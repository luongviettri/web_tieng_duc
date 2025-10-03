# app.py
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
import random
from datetime import datetime

# --- KHỞI TẠO ỨNG DỤNG VÀ DATABASE ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-very-secret-key-for-phase-4'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # Sử dụng file database.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Chuyển hướng đến trang login nếu chưa đăng nhập

# --- ĐỊNH NGHĨA CÁC BẢNG TRONG DATABASE (MODELS) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    results = db.relationship('QuizResult', backref='user', lazy=True) # Liên kết với kết quả quiz

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Hàm cần thiết cho Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- CÁC HÀM TẢI DỮ LIỆU CŨ ---
def load_vocab():
    with open('vocabulary.json', 'r', encoding='utf-8') as f: return json.load(f)
def load_grammar():
    with open('grammar.json', 'r', encoding='utf-8') as f: return json.load(f)

# --- CÁC TRANG CƠ BẢN ---
@app.route('/')
def index(): return render_template('index.html')
@app.route('/vocabulary')
def vocabulary(): return render_template('vocabulary.html', vocab=load_vocab())
@app.route('/grammar')
def grammar(): return render_template('grammar.html', grammar_lessons=load_grammar())
@app.route('/exercises')
def exercises(): return render_template('exercises.html', topics=list(load_vocab().keys()))
@app.route('/quiz/<topic_name>')
def quiz(topic_name):
    # (Code phần quiz giữ nguyên như Giai đoạn 3)
    vocab_data = load_vocab()
    words_for_topic = vocab_data[topic_name]
    all_vietnamese_words = [word['vietnamese'] for category in vocab_data.values() for word in category]
    questions = []
    for word_data in words_for_topic:
        correct_answer = word_data['vietnamese']
        wrong_answers = random.sample([v for v in all_vietnamese_words if v != correct_answer], 3)
        choices = wrong_answers + [correct_answer]
        random.shuffle(choices)
        questions.append({"german": word_data['german'], "choices": choices, "correct": correct_answer})
    session['quiz_answers'] = {q['german']: q['correct'] for q in questions}
    session['current_topic'] = topic_name
    return render_template('quiz.html', questions=questions, topic=topic_name)

# --- CẬP NHẬT TRANG KẾT QUẢ ĐỂ LƯU VÀO DATABASE ---
@app.route('/result', methods=['POST'])
def result():
    user_answers = request.form
    correct_answers = session.get('quiz_answers', {})
    score = 0
    results_summary = []
    for german_word, correct_answer in correct_answers.items():
        user_answer = user_answers.get(german_word)
        if user_answer == correct_answer: score += 1
        results_summary.append({"german": german_word, "user_answer": user_answer, "correct_answer": correct_answer, "is_correct": user_answer == correct_answer})
    
    # Nếu người dùng đã đăng nhập, lưu kết quả vào DB
    if current_user.is_authenticated:
        new_result = QuizResult(
            topic=session.get('current_topic', 'Unknown'),
            score=score,
            total=len(correct_answers),
            user_id=current_user.id
        )
        db.session.add(new_result)
        db.session.commit()

    return render_template('result.html', score=score, total=len(correct_answers), results=results_summary)

# --- CÁC TRANG MỚI: ĐĂNG KÝ, ĐĂNG NHẬP, ĐĂNG XUẤT, DASHBOARD ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Kiểm tra username đã tồn tại chưa
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại!', 'danger')
            return redirect(url_for('register'))
            
        # Băm mật khẩu và tạo user mới
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Đăng nhập thất bại. Vui lòng kiểm tra lại tên đăng nhập và mật khẩu.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Lấy tất cả kết quả của người dùng hiện tại, sắp xếp mới nhất lên đầu
    user_results = QuizResult.query.filter_by(user_id=current_user.id).order_by(QuizResult.timestamp.desc()).all()
    return render_template('dashboard.html', user_results=user_results)

# Chạy app (đã bỏ if __name__ == '__main__' để dùng lệnh flask)
if __name__ == '__main__':
    app.run(debug=True)