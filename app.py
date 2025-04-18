import io
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/flask_app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Models
class CustUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class SaleProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    image_data = db.Column(db.LargeBinary, nullable=True)
    image_mimetype = db.Column(db.String(50), nullable=True)

class BankUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(20), nullable=False)
    account_password = db.Column(db.String(100), nullable=False)

class PurchasedProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Pending")
    username = db.Column(db.String(150), nullable=False)  # Add this line

# Ensure tables exist
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = CustUser.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['username'] = user.username  # Still keep this
            session['customer_id'] = user.id     # ✅ Still keep this
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials.")

    return render_template('login.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Username and Password are required.', 'danger')
            return render_template('register.html')

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = CustUser(username=username, password=hashed_password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    else:
        flash('You need to log in first.', 'warning')
        return redirect(url_for('login'))

@app.route('/customer-sale')
def customer_sale():
    products = SaleProduct.query.all()
    return render_template('customer_sale.html', products=products)

@app.route('/update-product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    product = SaleProduct.query.get_or_404(product_id)

    if 'image' in request.files:
        image = request.files['image']
        if image and allowed_file(image.filename):
            product.image_data = image.read()
            product.image_mimetype = image.mimetype
            db.session.commit()
            flash('Product image updated successfully!', 'success')
        else:
            flash('Invalid file type.', 'danger')

    return redirect(url_for('customer_sale'))

@app.route('/product-sale-image/<int:product_id>')
def product_sale_image(product_id):
    product = SaleProduct.query.get_or_404(product_id)

    if product.image_data:
        return Response(product.image_data, mimetype=product.image_mimetype)
    else:
        return "No image found", 404

    @app.route('/buy-product/<int:product_id>', methods=['POST'])
    def buy_product(product_id):
        product = SaleProduct.query.get_or_404(product_id)
        quantity = int(request.form.get('quantity', 1))

        if quantity <= 0:
            flash("Invalid quantity.", "danger")
            return redirect(url_for('customer_sale'))

        if product.quantity >= quantity:
            # No stock deduction here
            return redirect(url_for('payment_page', product_id=product_id, qty=quantity))
        else:
            flash('Not enough stock for your request.', 'danger')
            return redirect(url_for('customer_sale'))

        
    @app.route('/payment/<int:product_id>')
    def payment_page(product_id):
        qty = int(request.args.get('qty', 1))
        product = SaleProduct.query.get_or_404(product_id)
        
        # Validate again in case someone changes URL manually
        if qty <= 0 or qty > product.quantity + qty:  # +qty because it's not deducted yet
            flash("Invalid purchase quantity.", "danger")
            return redirect(url_for('customer_sale'))

        total_price = qty * product.price
        return render_template('payment.html', product=product, quantity=qty, total_price=total_price)

    @app.route('/payment-success', methods=['POST'])
    def payment_success():
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])
        selected_bank = request.form.get('bank_name')

        product = SaleProduct.query.get_or_404(product_id)

        # Validate quantity again
        if quantity > product.quantity:
            flash('Payment failed: insufficient stock.', 'danger')
            return redirect(url_for('customer_sale'))

        # Simulate successful payment and confirm stock was already reduced
        flash(f'Payment successful via {selected_bank.capitalize()}. Thank you!', 'success')
        return redirect(url_for('customer_sale'))

    from flask import session

    @app.route('/process-payment', methods=['POST'])
    def process_payment():
        product_id = int(request.form.get('product_id'))
        quantity = int(request.form.get('quantity'))
        bank_name = request.form.get('bank_name')
        account_number = request.form.get('account_number')
        account_password = request.form.get('account_password')

        product = SaleProduct.query.get_or_404(product_id)

        # Validate bank info
        user = BankUser.query.filter_by(
            bank_name=bank_name,
            account_number=account_number,
            account_password=account_password
        ).first()

        if not user:
            return render_template('payment.html',
                                product=product,
                                quantity=quantity,
                                total_price=quantity * product.price,
                                message='Payment failed. Please check your bank details.',
                                error=True)

        if quantity > product.quantity:
            return render_template('payment.html',
                                product=product,
                                quantity=quantity,
                                total_price=quantity * product.price,
                                message='Payment failed: insufficient stock.',
                                error=True)

        # Deduct stock
        product.quantity -= quantity

        # Get logged-in customer's username
        customer_id = session.get('customer_id')
        cust_user = CustUser.query.get(customer_id)
        username = cust_user.username if cust_user else "Unknown"

        # Save purchase to PurchasedProduct
        purchased = PurchasedProduct(
            name=product.name,
            quantity=quantity,
            username=username,
        )
        db.session.add(purchased)
        db.session.commit()

        flash(f'Payment successful via {bank_name.capitalize()}. Thank you!', 'success')
        return redirect(url_for('customer_sale'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == "__main__":
    print("Starting Flask app...")
    app.run(debug=True)

