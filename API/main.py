from fastapi import FastAPI

app = FastAPI()

@app.get("/inventory")
def inventory():

    return [
        # Electronics
        {"product_id":"P001","product_name":"Wireless Mouse","category":"Electronics","current_stock":120,"today_sales":50,"remaining_stock":70},
        {"product_id":"P002","product_name":"Mechanical Keyboard","category":"Electronics","current_stock":40,"today_sales":20,"remaining_stock":20},
        {"product_id":"P003","product_name":"Bluetooth Speaker","category":"Electronics","current_stock":60,"today_sales":18,"remaining_stock":42},

        # Grocery
        {"product_id":"P004","product_name":"Basmati Rice 5kg","category":"Grocery","current_stock":200,"today_sales":35,"remaining_stock":165},
        {"product_id":"P005","product_name":"Sunflower Oil 1L","category":"Grocery","current_stock":150,"today_sales":45,"remaining_stock":105},
        {"product_id":"P006","product_name":"Wheat Flour 10kg","category":"Grocery","current_stock":100,"today_sales":25,"remaining_stock":75},

        # Fashion
        {"product_id":"P007","product_name":"Men's T-Shirt","category":"Fashion","current_stock":80,"today_sales":30,"remaining_stock":50},
        {"product_id":"P008","product_name":"Women's Jeans","category":"Fashion","current_stock":60,"today_sales":15,"remaining_stock":45},
        {"product_id":"P009","product_name":"Running Shoes","category":"Fashion","current_stock":50,"today_sales":12,"remaining_stock":38},

        # Home & Kitchen
        {"product_id":"P010","product_name":"Pressure Cooker","category":"Home & Kitchen","current_stock":40,"today_sales":8,"remaining_stock":32},
        {"product_id":"P011","product_name":"Mixer Grinder","category":"Home & Kitchen","current_stock":35,"today_sales":10,"remaining_stock":25},
        {"product_id":"P012","product_name":"Non-Stick Pan","category":"Home & Kitchen","current_stock":55,"today_sales":14,"remaining_stock":41},

        # Sports
        {"product_id":"P013","product_name":"Football","category":"Sports","current_stock":70,"today_sales":22,"remaining_stock":48},
        {"product_id":"P014","product_name":"Cricket Bat","category":"Sports","current_stock":45,"today_sales":9,"remaining_stock":36},
        {"product_id":"P015","product_name":"Yoga Mat","category":"Sports","current_stock":65,"today_sales":18,"remaining_stock":47},

        # Beauty
        {"product_id":"P016","product_name":"Face Wash","category":"Beauty","current_stock":90,"today_sales":28,"remaining_stock":62},
        {"product_id":"P017","product_name":"Shampoo","category":"Beauty","current_stock":120,"today_sales":40,"remaining_stock":80},
        {"product_id":"P018","product_name":"Body Lotion","category":"Beauty","current_stock":85,"today_sales":21,"remaining_stock":64},

        # Books
        {"product_id":"P019","product_name":"Python Programming","category":"Books","current_stock":30,"today_sales":6,"remaining_stock":24},
        {"product_id":"P020","product_name":"Data Science Handbook","category":"Books","current_stock":25,"today_sales":5,"remaining_stock":20},
        {"product_id":"P021","product_name":"AI Fundamentals","category":"Books","current_stock":20,"today_sales":4,"remaining_stock":16},

        # Toys
        {"product_id":"P022","product_name":"Building Blocks Set","category":"Toys","current_stock":60,"today_sales":16,"remaining_stock":44},
        {"product_id":"P023","product_name":"Remote Control Car","category":"Toys","current_stock":35,"today_sales":11,"remaining_stock":24},
        {"product_id":"P024","product_name":"Doll House","category":"Toys","current_stock":28,"today_sales":7,"remaining_stock":21},

        # Automotive
        {"product_id":"P025","product_name":"Car Phone Holder","category":"Automotive","current_stock":75,"today_sales":19,"remaining_stock":56},
        {"product_id":"P026","product_name":"Engine Oil","category":"Automotive","current_stock":90,"today_sales":23,"remaining_stock":67},
        {"product_id":"P027","product_name":"Bike Helmet","category":"Automotive","current_stock":50,"today_sales":13,"remaining_stock":37},

        # Office Supplies
        {"product_id":"P028","product_name":"A4 Paper Pack","category":"Office Supplies","current_stock":140,"today_sales":32,"remaining_stock":108},
        {"product_id":"P029","product_name":"Stapler","category":"Office Supplies","current_stock":45,"today_sales":8,"remaining_stock":37},
        {"product_id":"P030","product_name":"Whiteboard Marker Set","category":"Office Supplies","current_stock":65,"today_sales":15,"remaining_stock":50}
    ]