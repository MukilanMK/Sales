import smtplib
import imaplib
import email
from email.message import EmailMessage
import os
import time
from dotenv import load_dotenv

load_dotenv()

class EmailHelper:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        
        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        
        if not self.email_address or not self.email_password:
            print("Warning: EMAIL_ADDRESS or EMAIL_PASSWORD not set in .env. Real email functions will fail if called.")

    def send_email(self, to_address: str, subject: str, body: str) -> bool:
        if not self.email_address or not self.email_password:
            print(f"Skipping actual send to {to_address} (missing credentials)")
            return False
            
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = self.email_address
        msg['To'] = to_address

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Error sending email to {to_address}: {e}")
            return False

    def wait_for_reply(self, from_address: str, subject_keywords: list, timeout_seconds: int = 300, poll_interval: int = 15) -> str:
        """
        Polls the inbox for an unread message matching the sender and subject keywords.
        Returns the body of the message if found, otherwise returns an empty string.
        """
        if not self.email_address or not self.email_password:
            print(f"Skipping IMAP check for {from_address} (missing credentials).")
            return ""

        print(f"  ⏳ Waiting for reply from {from_address} (timeout in {timeout_seconds}s)...")
        end_time = time.time() + timeout_seconds
        
        while time.time() < end_time:
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
                mail.login(self.email_address, self.email_password)
                mail.select('inbox')
                
                # Format the search criteria
                search_criteria = f'(UNSEEN FROM "{from_address}")'
                status, messages = mail.search(None, search_criteria)
                
                if status == 'OK':
                    for num in messages[0].split():
                        status, data = mail.fetch(num, '(RFC822)')
                        if status == 'OK':
                            raw_email = data[0][1]
                            msg = email.message_from_bytes(raw_email)
                            subject = str(msg.get("Subject", ""))
                            
                            # Check if subject matches keywords
                            matches = all(keyword.lower() in subject.lower() for keyword in subject_keywords)
                            if matches:
                                # Found the email, get body
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        content_disposition = str(part.get("Content-Disposition"))
                                        if content_type == "text/plain" and "attachment" not in content_disposition:
                                            body += part.get_payload(decode=True).decode()
                                else:
                                    body = msg.get_payload(decode=True).decode()
                                
                                # Mark as read (fetch usually does this, but we explicitly do it too)
                                mail.store(num, '+FLAGS', '\\Seen')
                                mail.logout()
                                return body.strip()
                
                mail.logout()
            except Exception as e:
                print(f"Error checking email: {e}")
                
            time.sleep(poll_interval)
            
        print(f"  ❌ Timeout waiting for reply from {from_address}")
        return ""

    def fetch_recent_replies(self, expected_senders: list, limit: int = 10) -> dict:
        """
        Fetches the `limit` most recent emails from the inbox and checks if the sender
        matches any of the `expected_senders`.
        Returns a dictionary mapping matching sender emails to their email body.
        """
        if not self.email_address or not self.email_password:
            print("Skipping IMAP check (missing credentials).")
            return {}

        results = {}
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            mail.select('inbox')

            status, messages = mail.search(None, 'ALL')
            if status == 'OK':
                message_numbers = messages[0].split()
                # Get the last `limit` messages
                recent_numbers = message_numbers[-limit:] if len(message_numbers) > limit else message_numbers
                
                # Fetch them in reverse (newest first) to prioritize latest replies
                for num in reversed(recent_numbers):
                    status, data = mail.fetch(num, '(RFC822)')
                    if status == 'OK':
                        raw_email = data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # Extract sender email
                        from_header = str(msg.get("From", ""))
                        sender_email = ""
                        if "<" in from_header and ">" in from_header:
                            sender_email = from_header.split("<")[1].split(">")[0].strip().lower()
                        else:
                            sender_email = from_header.strip().lower()

                        expected_senders_lower = [e.lower() for e in expected_senders]
                        
                        if sender_email in expected_senders_lower and sender_email not in results:
                            # Found the email, get body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    content_type = part.get_content_type()
                                    content_disposition = str(part.get("Content-Disposition"))
                                    if content_type == "text/plain" and "attachment" not in content_disposition:
                                        body += part.get_payload(decode=True).decode()
                            else:
                                body = msg.get_payload(decode=True).decode()
                            
                            results[sender_email] = body.strip()
                            mail.store(num, '+FLAGS', '\\Seen')

            mail.logout()
        except Exception as e:
            print(f"Error fetching recent emails: {e}")
            
        return results
