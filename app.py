from flask import Flask, render_template, request, redirect, url_for, flash, session
import firebase_admin
from firebase_admin import credentials, firestore
from flask import jsonify
import smtplib
from email.message import EmailMessage
from flask import request
from datetime import datetime, timedelta

app = Flask(__name__)

if not firebase_admin._apps:
    cred = credentials.Certificate('walkwins-4c968-firebase-adminsdk-fbsvc-d8e3842614.json')  # Download this from Firebase Console
    firebase_admin.initialize_app(cred)
db = firestore.client()

app.secret_key = 'your_secret_key'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == 'Walkwinsind@gmail.com' and password == 'Incorrects@31':
            session['user'] = email
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/api/requests')
def get_requests():
    users_ref = db.collection('users')
    docs = users_ref.stream()
    user_list = []
    for doc in docs:
        data = doc.to_dict()
        withdraw_amount = data.get('withdraw_amount')
        if withdraw_amount is not None and withdraw_amount > 0:
            user_list.append({
                'user_id': doc.id,
                'email': data.get('email', ''),
                'username': data.get('username', ''),
                'payment_details': data.get('payment_details', ''),
                'withdraw_amount': withdraw_amount
            })
    return jsonify(user_list)

@app.route('/api/approve_payment', methods=['POST'])
def approve_payment():
    data = request.get_json()
    email = data.get('email')
    user_id = data.get('user_id')
    if not email or not user_id:
        return jsonify({'message': 'Email or user_id not provided'}), 400

    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    if not user_doc.exists:
        return jsonify({'message': 'User not found'}), 404

    user_data = user_doc.to_dict()
    withdraw_amount = user_data.get('withdraw_amount', 0)
    if not withdraw_amount or withdraw_amount <= 0:
        return jsonify({'message': 'No withdrawable amount'}), 400

    # Prepare transaction data
    transaction_data = {
        'amount': withdraw_amount,
        # 'timestamp': datetime.utcnow() + timedelta(hours=5, minutes=30)
        'timestamp': datetime.utcnow()
    }

    try:
        # Add to transactions subcollection
        transactions_ref = user_ref.collection('transactions')
        transactions_ref.add(transaction_data)

        # Set withdraw_amount to 0
        user_ref.update({'withdraw_amount': 0})

        # Send email to user
        SMTP_SERVER = 'smtp.gmail.com'
        SMTP_PORT = 587
        SMTP_USER = 'Walkwinsind@gmail.com'
        SMTP_PASS = 'llys vcjr fdkj rpoj'

        msg = EmailMessage()
        msg['Subject'] = 'Payment Credited'
        msg['From'] = SMTP_USER
        msg['To'] = email
        msg.set_content(f'Your payment of {withdraw_amount} has been credited.')

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        return jsonify({'message': 'Payment credited and user notified!'})
    except Exception as e:
        return jsonify({'message': f'Failed to credit payment: {str(e)}'}), 500

@app.route('/api/send_ineligible_mail', methods=['POST'])
def send_ineligible_mail():
    data = request.get_json()
    print('Received data:', data)
    email = data.get('email')
    user_id = data.get('user_id')
    if not email or not user_id:
        print('No email or user_id provided')
        return jsonify({'message': 'Email or user_id not provided'}), 400

    # Configure your SMTP settings here
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    SMTP_USER = 'Walkwinsind@gmail.com'
    SMTP_PASS = 'llys vcjr fdkj rpoj'

    msg = EmailMessage()
    msg['Subject'] = 'Payment Ineligibility'
    msg['From'] = SMTP_USER
    msg['To'] = email
    msg.set_content('You are ineligible for payment.')

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        # Update withdraw_amount in Firestore
        db.collection('users').document(user_id).update({'withdraw_amount': 0})
        return jsonify({'message': 'Ineligible mail sent!'})
    except Exception as e:
        return jsonify({'message': f'Failed to send mail or update Firestore: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
