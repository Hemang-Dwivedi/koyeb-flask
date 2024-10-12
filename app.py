from flask import Flask, jsonify, request
from flask_cors import CORS  # Import flask_cors
from xata.client import XataClient
from datetime import datetime
import bcrypt  # For hashing passwords
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# SMTP email configuration
EMAIL_HOST = "smtp.gmail.com"  # Gmail SMTP
EMAIL_PORT = 587
EMAIL_USER = "adapbl24@gmail.com"
EMAIL_PASS = "jwyj gfru aldz rkcq" 

app = Flask(__name__)
CORS(allow_headers="Access-Control-Allow-Origin: *")
CORS(app)  # Enable CORS for all routes

# Initialize Xata client
api_key = "xau_Rj6W3ynrvbDuhXb4Bkdmlk0h5Q7LyAOn3"
workspace_url = "https://ADA-PBL.xata.sh/db/main"
try:
    xata = XataClient(api_key=api_key, db_url="https://Hemang-Dwivedi-s-workspace-ar76ro.eu-central-1.xata.sh/db/ADA-PBL:main")
except Exception as e:
    print(f"Error initializing Xata client: {e}")

# Define collection names for Xata
USERS_COLLECTION = "Users"
PRODUCTS_COLLECTION = "Products"
ORDERS_COLLECTION = "Orders"
INVOICES_COLLECTION = "Invoices"
CART_COLLECTION = "Cart"



def generate_invoice_number():
    # Get the current timestamp in the format YYYYMMDD-HHMMSS
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')

    # Generate a random 6-digit number
    random_number = random.randint(100000, 999999)

    # Combine timestamp and random number to create invoice number
    invoice_number = f"INV-{timestamp}-{random_number}"

    return invoice_number


# Route to create a new user (register)
@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    username = data.get('username')
    password = data.get('password')  # Store hashed password
    email = data.get('email')
    role = data.get('role', 'buyer')  # Default role is 'buyer'

    # Hash the password before saving it (recommended)
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    user_data = {
        "username": username,
        "password": hashed_password.decode('utf-8'),  # Store as a string
        "email": email,
        "role": role
    }
    
    # Insert into Xata
    xata.records().insert(USERS_COLLECTION, user_data)
    return jsonify({'message': 'User registered successfully'}), 201

# Route to login
# Route to login
@app.route('/login', methods=['POST'])
def login_user():
    data = request.json
    email = data.get('username')
    password = data.get('password')

    # Fetch user by email
    users = xata.data().query(USERS_COLLECTION, {"columns": ["username", "password", "role", "xata_id"]})

    # Check if user exists
    if len(users['records']) == 0:
        return jsonify({'message': 'User not found'}), 404
    # Loop through users to verify credentials
    for user in users['records']:
        # Verify the username matches the email
        
        if user['username'] == email:
            
            # Verify the password
            if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                # Login successful
                return jsonify({'message': 'Login successful', 'user': user}), 200
            else:
                # Invalid password
                return jsonify({'message': 'Invalid credentials'}), 401

    # If no user matches, return an error
    return jsonify({'message': 'User not found or invalid credentials'}), 404

def is_seller(user):
    return user.get('role') == 'seller'

# Route for a seller to add products
@app.route('/seller/add-product', methods=['POST'])
def add_product():
    data = request.json
    user_id = data.get('user_id')
    role = data.get('role')  # Ensure seller is authenticated by providing user_id
    product_name = data.get('name')
    description = data.get('description', '')
    price = data.get('price')
    stock = data.get('stock', 0)

    # Fetch user to ensure they are a seller
    user = xata.records().get(USERS_COLLECTION, user_id)

    # Check if the user exists and is a seller
    if not user:
        return jsonify({'message': 'Unauthorized: Only sellers can add products'}), 403
    # Create product data
    product_data = {
        "name": product_name,
        "description": description,
        "price": int(price),
        "stock": int(stock),
        "seller_id": user_id  # Link product to the seller
    }

    # Insert into the Products collection
    try:
        dataa = xata.records().insert(PRODUCTS_COLLECTION, product_data)
    except (e):
        print(e)

    return jsonify({'message': 'Product added successfully'}), 201



# Route to get all products
@app.route('/products', methods=['GET'])
def get_products():
    products = xata.data().query(PRODUCTS_COLLECTION, {
        "columns": ["name", "description",  "price", "stock"]
        }
    )
    return jsonify(products["records"]), 200

# Route to create an order
@app.route('/order', methods=['POST'])
def create_order():
    data = request.json
    user_id = data.get('user_id')
    total_amount = data.get('total_amount')

    order_data = {
        "user_id": user_id,
        "total_amount": total_amount,
        "status": "pending"
    }

    # Insert into Xata
    order = xata.records().insert(ORDERS_COLLECTION, order_data)
    return jsonify(order), 201

# Route to create an invoice for an order
@app.route('/invoice', methods=['POST'])
def create_invoice():
    data = request.json
    order_id = data.get('order_id')
    total_amount = data.get('total_amount')

    invoice_number = generate_invoice_number()
    invoice_data = {
        "order_id": order_id,
        "invoice_number": invoice_number,
        "total_amount": total_amount,
        "status": "unpaid"
    }

    # Insert into Xata
    invoice = xata.records().insert(INVOICES_COLLECTION, invoice_data)

    order = xata.records().get(ORDERS_COLLECTION, order_id)
    
    user_id = order.get('user_id')
    user = xata.records().get(USERS_COLLECTION, user_id.get('id'))
    
    user_email = user.get('email')

    # Send the invoice email
    send_invoice_email(user_email, invoice_number, total_amount, order_id)

    return jsonify({'message': 'Invoice created successfully', 'invoice_number': invoice_number}), 201

# Route to add a product to the cart
@app.route('/cart', methods=['POST'])
def add_to_cart():
    data = request.json
    user_id = data.get('user_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)  # Default quantity is 1

    # Check if user_id and product_id are provided
    if not user_id or not product_id:
        return jsonify({'message': 'User ID and Product ID are required'}), 400

    # Create cart item data
    cart_item_data = {
        "user_id": user_id,
        "product_id": product_id,
        "quantity": quantity
    }

    # Insert into Xata
    try:
        dataa = xata.records().insert(CART_COLLECTION, cart_item_data)
        
        return jsonify({'message': 'Product added to cart successfully'}), 201
    except Exception as e:
        return jsonify({'message': f'Error adding product to cart: {str(e)}'}), 500

@app.route('/cart/<user_id>', methods=['GET'])
def get_cart(user_id):
    # Fetch cart items for the user
    cart_items = xata.data().query(CART_COLLECTION, {"columns": ["product_id", "user_id", "quantity"]})
    #, {filter: {"user_id.xata_id": str(user_id)}}
    
    return jsonify(cart_items['records']), 200

# Route to delete a product from the cart
@app.route('/cart', methods=['DELETE'])
def delete_from_cart():
    data = request.json
    user_id = data.get('user_id')
    cart_id = data.get('id')

    # Check if user_id and product_id are provided
    if not user_id or not cart_id:
        return jsonify({'message': 'User ID and Product ID are required'}), 400

    # Filter to find the cart item to delete
    try:
        # Find the cart item (assuming user_id and product_id uniquely identify a cart item)
        cart_items = xata.data().query(CART_COLLECTION, { "filter":{
            "user_id": user_id,
            "id": cart_id
        }
        })

        # If no matching cart item found, return error
        if len(cart_items['records']) == 0:
            return jsonify({'message': 'Cart item not found'}), 404

        xata.records().delete(CART_COLLECTION, cart_id)
        return jsonify({'message': 'Product removed from cart successfully'}), 200

    except Exception as e:
        return jsonify({'message': f'Error deleting product from cart: {str(e)}'}), 500


def send_invoice_email(user_email, invoice_number, total_amount, order_id):
    try:
        # Create the email object
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = user_email
        msg['Subject'] = f"Invoice for your purchase, Invoice number: {invoice_number}"

        # Create the email body
        body = f"""
        <h1>Your Invoice</h1>
        <p>Thank you for your purchase! Here is your invoice:</p>
        <p>Invoice Number: {invoice_number}</p>
        <p>Total Amount: ${total_amount}</p>
        <p>We hope you enjoy your products!</p>
        """
        msg.attach(MIMEText(body, 'html'))

        # Setup the email server
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()  # Secure the connection
        server.login(EMAIL_USER, EMAIL_PASS)

        # Send the email
        try:
            server.sendmail(EMAIL_USER, user_email, msg.as_string())
        except  Exception as e:
            print(e)

        server.quit()

        print(f"Invoice email sent to {user_email}")
        return True

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


# Route to mark an invoice as paid
@app.route('/invoice/<invoice_id>/pay', methods=['POST'])
def mark_invoice_as_paid(invoice_id):
    # Update invoice status to 'paid'
    xata.records().update(INVOICES_COLLECTION, invoice_id, {"status": "paid"})
    return jsonify({'message': 'Invoice marked as paid'}), 200

# Route to get all orders for a user
@app.route('/orders/<user_id>', methods=['GET'])
def get_orders(user_id):
    orders = xata.records().get(ORDERS_COLLECTION, {"user_id": user_id})
    return jsonify(orders), 200

# Route to update order status
@app.route('/order/<order_id>/status', methods=['POST'])
def update_order_status(order_id):
    data = request.json
    status = data.get('status', 'pending')
    xata.records().update(ORDERS_COLLECTION, order_id, {"status": status})
    return jsonify({'message': 'Order status updated'}), 200

# Route to view user details
@app.route('/user/<user_id>', methods=['GET'])
def get_user(user_id):
    user = xata.records().get(USERS_COLLECTION, user_id)
    return jsonify(user), 200

if __name__ == '__main__':
    app.run(debug=True)
