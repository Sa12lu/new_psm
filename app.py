import io
import os
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:GaQSDgaPsJnHGflsOhvogTsKqKmmexIm@tramway.proxy.rlwy.net:31763/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


#Xampp
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/flask_app'
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Models
class CustUser(db.Model):
    __tablename__ = 'cust_user'
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
    username = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('cust_user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # add NEW time date
    sale_product_id = db.Column(db.Integer, db.ForeignKey('sale_product.id'), nullable=False)  # ✅ NEW

class GiftBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gift_name = db.Column(db.String(100), nullable=False)  # Added gift name 
    image_data = db.Column(db.LargeBinary, nullable=True)
    image_mimetype = db.Column(db.String(50))
    description = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Integer, nullable=False)

class Booked(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gift_id = db.Column(db.Integer, db.ForeignKey('gift_booking.id'), nullable=False)  # ← new line
    gift_name = db.Column(db.String(100), nullable=False)  # ← Add this line
    description = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    datetime = db.Column(db.DateTime, default=datetime.utcnow)
    customer_name = db.Column(db.String(150), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('cust_user.id'))  
    status = db.Column(db.String(50), default='Pending')
    notified = db.Column(db.Boolean, default=False)



# Create tables
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
            session.clear()
            session['username'] = user.username
            session['customer_id'] = user.id
            print(f"[LOGIN] User: {user.username}, ID: {user.id} has logged in.")
            return render_template(
                'login.html',
                message='Login successful!',
                category='success',
                redirect_url=url_for('dashboard')
            )
        else:
            return render_template(
                'login.html',
                message='Invalid credentials.',
                category='danger'
            )

    return render_template('login.html', message=None, category=None)




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
    if 'username' not in session or 'customer_id' not in session:
        flash('You need to log in first.', 'warning')
        return redirect(url_for('login'))

    customer_id = session['customer_id']

    # Recent individual lists
    recent_purchases = PurchasedProduct.query\
        .filter_by(user_id=customer_id)\
        .order_by(PurchasedProduct.timestamp.desc())\
        .all()

    recent_bookings = Booked.query\
        .filter_by(customer_id=customer_id)\
        .order_by(Booked.datetime.desc())\
        .all()

    # Combine and tag activities with unified timestamp
    combined_activities = []

    for p in recent_purchases:
        combined_activities.append({
            'type': 'purchase',
            'name': p.name,
            'quantity': p.quantity,
            'timestamp': p.timestamp
        })

    for b in recent_bookings:
        combined_activities.append({
            'type': 'booking',
            'gift_name': b.gift_name,
            'quantity': b.quantity,
            'status': b.status,
            'timestamp': b.datetime
        })

    # Sort by time and limit to latest 5 entries
    combined_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    combined_activities = combined_activities[:5]

    # Image slides
    sale_products = SaleProduct.query.filter(SaleProduct.image_data != None).limit(5).all()
    gift_bookings = GiftBooking.query.filter(GiftBooking.image_data != None).limit(5).all()

    return render_template(
        'dashboard.html',
        username=session['username'],
        combined_activities=combined_activities,  # ✅ Now passed to template
        sale_products=sale_products,
        gift_bookings=gift_bookings
    )


@app.route('/customer-sale')
def customer_sale():
    customer_id = session.get('customer_id')
    if not customer_id:
        flash('You must be logged in to view this page.', 'danger')
        return redirect(url_for('login'))

    products = SaleProduct.query.all()
    purchased_products = PurchasedProduct.query.filter_by(user_id=customer_id).all()

    return render_template('customer_sale.html',
                           products=products,
                           purchased_products=purchased_products)

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
        return redirect(url_for('payment_page', product_id=product_id, qty=quantity))
    else:
        flash('Not enough stock for your request.', 'danger')
        return redirect(url_for('customer_sale'))

@app.route('/payment/<int:product_id>')
def payment_page(product_id):
    qty = int(request.args.get('qty', 1))
    product = SaleProduct.query.get_or_404(product_id)

    if qty <= 0 or qty > product.quantity + qty:
        flash("Invalid purchase quantity.", "danger")
        return redirect(url_for('customer_sale'))

    total_price = qty * product.price
    return render_template('payment.html', product=product, quantity=qty, total_price=total_price)

@app.route('/process-payment', methods=['POST'])
def process_payment():
    product_id = int(request.form.get('product_id'))
    quantity = int(request.form.get('quantity'))
    bank_name = request.form.get('bank_name')
    account_number = request.form.get('account_number')
    account_password = request.form.get('account_password')

    product = SaleProduct.query.get_or_404(product_id)

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

    product.quantity -= quantity

    customer_id = session.get('customer_id')
    cust_user = CustUser.query.get(customer_id)
    username = cust_user.username if cust_user else "Unknown"

    purchased = PurchasedProduct(
        name=product.name,
        quantity=quantity,
        username=username,
        user_id=customer_id,
        sale_product_id=product.id  # ✅ NEW: link back to SaleProduct
    )
    db.session.add(purchased)
    db.session.commit()

    flash(f'Payment successful via {bank_name.capitalize()}. Thank you!', 'success')
    return redirect(url_for('customer_sale'))

@app.route('/customer/gift-booking')
def customer_gift_booking():
    customer_id = session.get('customer_id')
    if not customer_id:
        return redirect(url_for('login'))

    gifts = GiftBooking.query.all()
    booked_gifts = Booked.query.filter_by(customer_id=customer_id).all()
    
    # Filter pending bookings only
    pending_bookings = [b for b in booked_gifts if b.status == 'Pending']

    # Only for bell icon (non-pending)
    non_pending_gifts = [b for b in booked_gifts if b.status != 'Pending']
    show_notification_dot = any(b.status != 'Pending' and not b.notified for b in booked_gifts)

    return render_template(
        "customer_gift_booking.html",
        gifts=gifts,
        booked_gifts=booked_gifts,
        pending_bookings=pending_bookings,  # Pass this for the modal
        non_pending_gifts=non_pending_gifts,
        show_notification_dot=show_notification_dot
    )




@app.route('/gift-image/<int:gift_id>')
def gift_image(gift_id):
    gift = GiftBooking.query.get_or_404(gift_id)
    if gift.image_data:
        return Response(gift.image_data, mimetype=gift.image_mimetype)
    return '', 404

@app.route('/book-gift/<int:gift_id>', methods=['POST'])
def book_gift(gift_id):
    if 'customer_id' not in session:
        flash("Please log in to book gifts.")
        return redirect(url_for('customer_gift_booking'))
    print(f"[BOOK] Session customer_id: {session.get('customer_id')}")
    quantity = int(request.form['quantity'])
    gift = GiftBooking.query.get_or_404(gift_id)

    print(f"Gift selected: {gift.description}, Available: {gift.amount}, Requested: {quantity}")

    if gift.amount < quantity:
        flash("Not enough gift quantity available.")
        return redirect(url_for('customer_gift_booking'))

    try:
        # Decrease available amount
        gift.amount -= quantity
        db.session.add(gift)

        # Get customer info
        customer = CustUser.query.get(session['customer_id'])
        if not customer:
            flash("Customer not found.")
            return redirect(url_for('customer_gift_booking'))

        # Add booking
        booking = Booked(
            gift_id=gift.id,  # ← new line
            gift_name=gift.gift_name,  # ← Add this line
            description=gift.description,
            price=gift.price,
            quantity=quantity,
            datetime=datetime.now(),
            status='Pending',
            customer_id=customer.id,
            customer_name=customer.username,
            notified=False  # New booking is unseen
        )
        db.session.add(booking)

        # Commit everything
        db.session.commit()
        flash("Gift booked successfully.")

    except SQLAlchemyError as e:
        print("Database error occurred:", str(e))
        db.session.rollback()
        flash("Booking failed due to a database error.")

    return redirect(url_for('customer_gift_booking'))

@app.route('/mark-notified')
def mark_notified():
    customer_id = session.get('customer_id')
    if customer_id:
        updated = Booked.query.filter(
            Booked.customer_id == customer_id,
            Booked.status != 'Pending',
            Booked.notified == False
        ).all()
        for b in updated:
            b.notified = True
        db.session.commit()
    return '', 204


@app.route('/booking-history')
def booking_history():
    customer_id = session.get('customer_id')
    if not customer_id:
        return jsonify([])

    history = Booked.query.filter(
        Booked.customer_id == customer_id,
        Booked.status != 'Pending'
    ).order_by(Booked.datetime.desc()).all()

    data = [{
        'gift_name': b.gift_name,
        'description': b.description,
        'price': b.price,
        'quantity': b.quantity,
        'datetime': b.datetime.strftime('%Y-%m-%d %H:%M:%S'),
        'status': b.status
    } for b in history]

    return jsonify(data)



@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('customer_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == "__main__":
    print("Starting Flask app...")
    app.run(debug=True)

