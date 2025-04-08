import tempfile
import os
from flask import Flask, render_template, request, redirect, url_for, make_response
from fpdf import FPDF
import boto3
from datetime import datetime

app = Flask(__name__)

# Simple in-memory cart
cart = []

# AWS S3 Configuration
S3_BUCKET = 'vk18ganesh'
S3_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
S3_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = "us-east-1"

# Sample products
products = [
    {"id": 1, "name": "Laptop", "price": 999.99},
    {"id": 2, "name": "Smartphone", "price": 699.99},
    {"id": 3, "name": "Headphones", "price": 149.99},
    {"id": 4, "name": "Tablet", "price": 349.99},
]

@app.route('/')
def index():
    return render_template('index.html', products=products)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = int(request.form.get('product_id'))
    quantity = int(request.form.get('quantity', 1))
    
    product = next((p for p in products if p['id'] == product_id), None)
    if product:
        cart.append({
            'product': product,
            'quantity': quantity,
            'subtotal': product['price'] * quantity
        })
    return redirect(url_for('view_cart'))

@app.route('/cart')
def view_cart():
    total = sum(item['subtotal'] for item in cart)
    return render_template('cart.html', cart=cart, total=total)

@app.route('/checkout', methods=['POST'])
def checkout():
    # Generate invoice PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Add invoice header
    pdf.cell(200, 10, txt="INVOICE", ln=1, align="C")
    pdf.ln(10)
    
    # Add order details
    pdf.cell(200, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=1)
    pdf.ln(5)
    
    # Add items
    pdf.cell(100, 10, txt="Item", border=1)
    pdf.cell(30, 10, txt="Quantity", border=1)
    pdf.cell(30, 10, txt="Price", border=1)
    pdf.cell(30, 10, txt="Subtotal", border=1, ln=1)
    
    total = 0
    for item in cart:
        product = item['product']
        pdf.cell(100, 10, txt=product['name'], border=1)
        pdf.cell(30, 10, txt=str(item['quantity']), border=1)
        pdf.cell(30, 10, txt=f"${product['price']:.2f}", border=1)
        pdf.cell(30, 10, txt=f"${item['subtotal']:.2f}", border=1, ln=1)
        total += item['subtotal']
    
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"TOTAL: ${total:.2f}", ln=1, align="R")
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"invoice_{timestamp}.pdf"
    
    # Create a temporary file that works on all platforms
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        temp_path = tmp_file.name
        pdf.output(temp_path)
    
    try:
        # Upload to S3
        s3 = boto3.client(
            's3',
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY
        )
        
        s3.upload_file(temp_path, S3_BUCKET, f"invoices/{filename}")
        
        # Clear the cart after successful upload
        cart.clear()
        
        # Return the PDF for immediate download
        with open(temp_path, 'rb') as f:
            pdf_data = f.read()
        
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        return response
        
    except Exception as e:
        # Clean up the temporary file in case of error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return f"Error uploading invoice: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)