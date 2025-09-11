from flask import Flask, render_template, request, redirect, url_for, flash, session
import firebase_admin
from firebase_admin import credentials, firestore
from flask import jsonify
import smtplib
from email.message import EmailMessage
from flask import request
from datetime import datetime, timedelta
import sys
import os
import webbrowser
from threading import Timer


# def resource_path(relative_path):
#     """ Get absolute path to resource, works for dev and for PyInstaller """
#     try:
#         # PyInstaller creates a temp folder and stores path in _MEIPASS
#         base_path = sys._MEIPASS
#     except Exception:
#         base_path = os.path.abspath(".")

#     return os.path.join(base_path, relative_path)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

if not firebase_admin._apps:
    # cred = credentials.Certificate(resource_path('walkwins-4c968-firebase-adminsdk-fbsvc-d8e3842614.json'))  # Download this from Firebase Console
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

@app.route('/api/approved')
def get_approved():
    users_ref = db.collection('users')
    users = users_ref.stream()
    approved_list = []
    for user_doc in users:
        user_data = user_doc.to_dict()
        user_id = user_doc.id
        email = user_data.get('email', '')
        username = user_data.get('username', '')
        transactions_ref = users_ref.document(user_id).collection('transactions')
        transactions = list(transactions_ref.stream())
        if not transactions:
            continue  # Skip users with no transactions
        for txn_doc in transactions:
            txn = txn_doc.to_dict()
            approved_list.append({
                'user_id': user_id,
                'email': email,
                'username': username,
                'amount': txn.get('amount', ''),
                'timestamp': txn.get('timestamp', '')
            })
    # Sort by timestamp descending (optional)
    approved_list.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(approved_list)

@app.route('/api/voucher_requests')
def get_voucher_requests():
    users_ref = db.collection('users')
    docs = users_ref.stream()
    voucher_list = []
    for doc in docs:
        data = doc.to_dict()
        voucher_amount = data.get('voucher_amount')
        if voucher_amount is not None and voucher_amount > 0:
            voucher_list.append({
                'user_id': doc.id,
                'email': data.get('email', ''),
                'username': data.get('username', ''),
                'voucher_amount': voucher_amount
            })
    return jsonify(voucher_list)

@app.route('/api/reject_voucher', methods=['POST'])
def reject_voucher():
    data = request.get_json()
    email = data.get('email')
    user_id = data.get('user_id')
    if not email or not user_id:
        return jsonify({'message': 'Email or user_id not provided'}), 400

    # Configure your SMTP settings here
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    SMTP_USER = 'Walkwinsind@gmail.com'
    SMTP_PASS = 'llys vcjr fdkj rpoj'

    msg = EmailMessage()
    msg['Subject'] = 'Voucher Request Rejected'
    msg['From'] = SMTP_USER
    msg['To'] = email
    msg.set_content('Your voucher request has been rejected and your voucher amount has been reset to 0.')

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        # Update voucher_amount in Firestore
        db.collection('users').document(user_id).update({'voucher_amount': 0})
        return jsonify({'message': 'Voucher rejection mail sent!'})
    except Exception as e:
        return jsonify({'message': f'Failed to send mail or update Firestore: {str(e)}'}), 500

@app.route('/api/approve_voucher', methods=['POST'])
def approve_voucher():
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
    voucher_amount = user_data.get('voucher_amount', 0)
    if not voucher_amount or voucher_amount <= 0:
        return jsonify({'message': 'No voucher amount'}), 400

    # Prepare voucher data
    voucher_data = {
        'amount': voucher_amount,
        'timestamp': datetime.utcnow()
    }

    try:
        # Add to vouchers subcollection
        vouchers_ref = user_ref.collection('vouchers')
        vouchers_ref.add(voucher_data)

        # Set voucher_amount to 0
        user_ref.update({'voucher_amount': 0})

        # Send email to user
        SMTP_SERVER = 'smtp.gmail.com'
        SMTP_PORT = 587
        SMTP_USER = 'Walkwinsind@gmail.com'
        SMTP_PASS = 'llys vcjr fdkj rpoj'

        msg = EmailMessage()
        msg['Subject'] = 'Voucher Approved'
        msg['From'] = SMTP_USER
        msg['To'] = email
        msg.set_content(f'Your voucher request of {voucher_amount} has been approved.')

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        return jsonify({'message': 'Voucher approved and user notified!'})
    except Exception as e:
        return jsonify({'message': f'Failed to approve voucher: {str(e)}'}), 500

@app.route('/api/voucher_approved')
def get_voucher_approved():
    users_ref = db.collection('users')
    users = users_ref.stream()
    approved_list = []
    for user_doc in users:
        user_data = user_doc.to_dict()
        user_id = user_doc.id
        email = user_data.get('email', '')
        username = user_data.get('username', '')
        vouchers_ref = users_ref.document(user_id).collection('vouchers')
        vouchers = list(vouchers_ref.stream())
        if not vouchers:
            continue  # Skip users with no vouchers
        for voucher_doc in vouchers:
            voucher = voucher_doc.to_dict()
            approved_list.append({
                'user_id': user_id,
                'email': email,
                'username': username,
                'amount': voucher.get('amount', ''),
                'timestamp': voucher.get('timestamp', '')
            })
    # Sort by timestamp descending (optional)
    approved_list.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(approved_list)

if __name__ == '__main__':
    app.run(debug=True)

# if __name__ == "__main__":
#     # URL to open
#     url = "http://127.0.0.1:5000"
#     Timer(3, lambda: webbrowser.open(url)).start()
#     app.run()