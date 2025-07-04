from flask import Flask, render_template, request, redirect, url_for, session
import boto3
import uuid
import random

app = Flask(_name_)
app.secret_key = '9a4f90b2b6df594f2e16f6c1f3d9e0ab0cd431c0f0176a2544e740c94cb75a0e'

# AWS setup
region = 'us-east-1'
dynamodb = boto3.resource('dynamodb', region_name=region)
sns = boto3.client('sns', region_name=region)

sns_topic_arn = 'arn:aws:sns:us-east-1:311141554074:MyTopic'  # Replace with your real topic ARN

def send_booking_email(email, movie, date, time, seat, booking_id):
    message = f"""
    🎟 Booking Confirmed!

    Movie: {movie}
    Date: {date}
    Time: {time}
    Seat(s): {seat}
    Booking ID: {booking_id}

    Thank you for booking with us!
    """
    try:
        sns.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject="Your Movie Ticket Booking Confirmation"
        )
        return True
    except Exception as e:
        print(f"Error sending email via SNS: {e}")
        return False

users_table = dynamodb.Table('users')
bookings_table = dynamodb.Table('bookings')

# Static movie list
movies = [
    {"id": 2, "name": "Hanuman", "time": "6:00 PM", "price": 150, "rating": 4.8, "image": "hanuman.jpeg"},
    {"id": 7, "name": "Retro", "time": "3:30 PM", "price": 180, "rating": 4.7, "image": "retro.jpeg"},
    {"id": 10, "name": "Hit-3:The Third Case", "time": "1:00 PM", "price": 160, "rating": 4.6, "image": "hit3.jpeg"},
    {"id": 4, "name": "Final Destination", "time": "5:00 PM", "price": 200, "rating": 4.9, "image": "fd.jpeg"},
    {"id": 9, "name": "Tillu Square", "time": "11:00 AM", "price": 140, "rating": 4.5, "image": "tillusquare.jpeg"},
    {"id": 1, "name": "Kabir Singh", "time": "8:00 PM", "price": 190, "rating": 4.4, "image": "kabirsingh.jpeg"},
    {"id": 6, "name": "Tiger-3", "time": "2:30 PM", "price": 170, "rating": 4.6, "image": "tiger3.jpeg"},
    {"id": 8, "name": "Mufasa:The Lion King", "time": "10:00 AM", "price": 160, "rating": 4.3, "image": "mufasa.jpeg"},
    {"id": 3, "name": "Maghadheera", "time": "4:30 PM", "price": 130, "rating": 4.2, "image": "magadheera.jpeg"},
    {"id": 5, "name": "Tourist Family", "time": "7:00 PM", "price": 175, "rating": 4.4, "image": "tourist.jpeg"},
]

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        user = users_table.get_item(Key={'email': email}).get('Item')

        if user and user['password'] == password:
            session['user'] = email
            session.permanent = True if remember else False
            return redirect(url_for('home'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')

        existing_user = users_table.get_item(Key={'email': email}).get('Item')
        if existing_user:
            return render_template('register.html', error='User already exists')

        # Basic phone formatting (E.164 format)
        if not phone.startswith('+'):
            phone = '+91' + phone  # Default country code, update as needed

        users_table.put_item(Item={'email': email, 'password': password, 'phone': phone})
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('home1.html')

@app.route('/movies')
def movies_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    query = request.args.get('q', '')
    filtered = [m for m in movies if query.lower() in m['name'].lower()]
    return render_template('movies.html', movies=filtered)

@app.route('/book/<int:id>', methods=['GET', 'POST'])
def book_ticket(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    movie = next((m for m in movies if m['id'] == id), None)
    if not movie:
        return "Movie not found.", 404
    if request.method == 'POST':
        name = request.form.get('name')
        tickets = request.form.get('tickets')
        if not name or not tickets:
            return render_template("book.html", movie=movie, error="Please fill all fields")
        try:
            tickets = int(tickets)
            booking_id = str(uuid.uuid4())

            bookings_table.put_item(Item={
                'user_email': session['user'],
                'booking_id': booking_id,
                'movie_name': movie['name'],
                'show_time': movie['time'],
                'tickets': tickets,
                'booked_by': name
            })

            # Send booking email via SNS
            send_booking_email(
                session['user'],
                movie['name'],
                "Today",
                movie['time'],
                tickets,
                booking_id
            )

            return render_template('success.html', movie=movie, name=name, tickets=tickets)
        except ValueError:
            return render_template("book.html", movie=movie, error="Invalid ticket number")
    return render_template('book.html', movie=movie)

@app.route('/admin')
def admin():
    all_bookings = bookings_table.scan().get('Items', [])
    return render_template('admin.html', bookings=all_bookings)

@app.route('/contact')
def contact():
    return render_template('contact_us.html')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form.get('email')
        user = users_table.get_item(Key={'email': email}).get('Item')
        if user:
            code = random.randint(1000, 9999)
            session['reset_code'] = code
            session['reset_email'] = email

            # Send SMS using AWS SNS
            message = f"Your Movie Magic verification code is: {code}"
            try:
                sns.publish(
                    PhoneNumber=user['phone'],
                    Message=message
                )
                return redirect(url_for('verify_code'))
            except Exception as e:
                return render_template('forgot_password.html', error=f"Failed to send code: {e}")
        else:
            return render_template('forgot_password.html', error="Email not registered.")
    return render_template('forgot_password.html')

@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        entered = request.form.get('code')
        if 'reset_code' in session and entered == str(session['reset_code']):
            return redirect(url_for('reset_password'))
        else:
            return render_template('verify_code.html', error="Invalid code. Try again.")
    return render_template('verify_code.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_pass = request.form.get('password')
        email = session.get('reset_email')
        if email:
            users_table.update_item(
                Key={'email': email},
                UpdateExpression='SET password = :p',
                ExpressionAttributeValues={':p': new_pass}
            )
            session.pop('reset_email', None)
            session.pop('reset_code', None)
            return redirect(url_for('login'))
        return "User not found."
    return render_template('reset_password.html')

if _name_ == '_main_':
    app.run(debug=True)