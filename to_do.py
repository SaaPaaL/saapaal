from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, User, Todo
import os
from functools import wraps
import re


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)


app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'todo.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)



def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("ابتدا وارد شوید", 'error')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated



@app.cli.command('init-db')
def init_db():
    with app.app_context():
        db.create_all()
        print(" Database created successfully.")



@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        if len(password) < 8:
            flash('رمز عبور باید حداقل ۸ کاراکتر باشد.', 'error')
            return redirect(url_for('register'))

        if not re.search(r'[A-Z]', password):
            flash('رمز باید حداقل یک حرف بزرگ انگلیسی داشته باشد.', 'error')
            return redirect(url_for('register'))

        if not re.search(r'[a-z]', password):
            flash('رمز باید حداقل یک حرف کوچک انگلیسی داشته باشد.', 'error')
            return redirect(url_for('register'))

        if not re.search(r'\d', password):
            flash('رمز باید حداقل یک عدد داشته باشد.', 'error')
            return redirect(url_for('register'))

        if not re.search(r'[^A-Za-z0-9]', password):
            flash('رمز باید حداقل یک علامت خاص مانند @ یا ! داشته باشد.', 'error')
            return redirect(url_for('register'))

        phone = request.form.get('phone') or None
        if phone:
            if not re.fullmatch(r'09\d{9}', phone):
                flash('شماره تلفن باید با 09 شروع شود و دقیقاً 11 رقم باشد.', 'error')
                return redirect(url_for('register'))

        birthday_s = request.form.get('birthday') or None
        national = request.form.get('national_id') or None

        if not username or not password:
            flash('نام کاربری و رمز عبور الزامی است', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('این نام کاربری قبلاً ثبت شده است', 'error')
            return redirect(url_for('register'))

        birthday = None
        if birthday_s:
            try:
                birthday = datetime.strptime(birthday_s, '%Y-%m-%d').date()
            except ValueError:
                flash('فرمت تاریخ تولد اشتباه است. از YYYY-MM-DD استفاده کنید', 'error')
                return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        new_user = User(username=username, password=hashed, phone=phone, birthday=birthday, national_id=national)
        db.session.add(new_user)
        db.session.commit()

        flash('ثبت‌نام با موفقیت انجام شد. حالا می‌توانید وارد شوید.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or url_for('todo_list')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('ورود موفقیت‌آمیز بود', 'success')
            return redirect(next_url)

        flash('نام کاربری یا رمز عبور اشتباه است', 'error')
        return redirect(url_for('login'))

    return render_template('login.html', next=next_url)



@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('خروج با موفقیت انجام شد.', 'info')
    return redirect(url_for('login'))

@app.route('/profile',methods= ['GET','POST'])
@login_required
def profile():
    user = User.query.get_or_404(session['user_id'])

    if request.method == 'POST':
        phone = request.form.get('phone') or None
        
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if phone:
            if not re.fullmatch(r'09\d{9}', phone):
                flash('شماره تلفن باید با 09 شروع شود و دقیقاً 11 رقم باشد.', 'error')
                return redirect(url_for('profile'))
        user.phone = phone 

        if new_password :
            if not check_password_hash(user.password,current_password):
                flash('رمز غبور فعلی اشتباه است.','error')
                return redirect(url_for('profile'))
            
            if new_password != confirm_password :
                flash('رمز عبور جدید با تکرار ان یکی نیست.','error')
                return redirect(url_for('profile'))
            user.password =generate_password_hash(new_password)
            flash('رمز عبور با موفقیعت عوض شد.','success')
        
        db.session.commit()
        flash('پروفایل با موفقغیت بروز رسانی شد.','success')
        return redirect(url_for('profile'))
    return render_template('profile.html',user=user)
    



@app.route('/')
@login_required
def todo_list():
    user_id = session['user_id']
    q = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'deadline')
    order = request.args.get('order', 'asc')

    todos_query = Todo.query.filter_by(user_id=user_id)

    if q:
        todos_query = todos_query.filter(
            (Todo.title.contains(q)) | (Todo.description.contains(q))
        )

    key = Todo.created_at if sort_by == 'date' else Todo.deadline

    if order == 'desc':
        todos_query = todos_query.order_by(key.desc().nulls_last())
    else:
        todos_query = todos_query.order_by(key.asc().nulls_last())

    todos = todos_query.all()
    return render_template('todo_list.html', todos=todos, q=q, sort_by=sort_by, order=order)



@app.route('/todo/create', methods=['GET', 'POST'])
@login_required
def todo_create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description') or None
        deadline_s = request.form.get('deadline') or None
        priority = request.form.get('priority') or 'medium'

        deadline = None
        if deadline_s:
            try:
                deadline = datetime.strptime(deadline_s, '%Y-%m-%d %H:%M')
            except ValueError:
                try:
                    deadline = datetime.strptime(deadline_s, '%Y-%m-%d')
                except ValueError:
                    flash('فرمت تاریخ/زمان اشتباه است', 'error')
                    return redirect(url_for('todo_create'))

        new_todo = Todo(
            title=title,
            description=description,
            deadline=deadline,
            priority=priority,
            user_id=session['user_id']
        )
        db.session.add(new_todo)
        db.session.commit()

        flash('تسک با موفقیت ایجاد شد', 'success')
        return redirect(url_for('todo_list'))

    return render_template('todo_form.html', todo=None)



@app.route('/todo/<int:todo_id>')
@login_required
def todo_detail(todo_id):
    t = Todo.query.filter_by(id=todo_id, user_id=session['user_id']).first_or_404()
    return render_template('todo_detail.html', todo=t)



@app.route('/todo/<int:todo_id>/edit', methods=['GET', 'POST'])
@login_required
def todo_edit(todo_id):
    t = Todo.query.filter_by(id=todo_id, user_id=session['user_id']).first_or_404()

    if request.method == 'POST':
        t.title = request.form.get('title', '').strip()
        t.description = request.form.get('description') or None
        deadline_s = request.form.get('deadline') or None

        if deadline_s:
            try:
                t.deadline = datetime.strptime(deadline_s, '%Y-%m-%d %H:%M')
            except ValueError:
                try:
                    t.deadline = datetime.strptime(deadline_s, '%Y-%m-%d')
                except ValueError:
                    flash('فرمت تاریخ اشتباه است', 'error')
                    return redirect(url_for('todo_edit', todo_id=t.id))
        else:
            t.deadline = None

        t.priority = request.form.get('priority') or 'medium'
        db.session.commit()

        flash('تسک ویرایش شد', 'success')
        return redirect(url_for('todo_detail', todo_id=t.id))

    return render_template('todo_form.html', todo=t)



@app.route('/todo/<int:todo_id>/delete', methods=['POST'])
@login_required
def todo_delete(todo_id):
    t = Todo.query.filter_by(id=todo_id, user_id=session['user_id']).first_or_404()
    db.session.delete(t)
    db.session.commit()
    flash('تسک حذف شد', 'success')
    return redirect(url_for('todo_list'))



@app.route('/todo/<int:todo_id>/toggle', methods=['POST'])
@login_required
def todo_toggle(todo_id):
    t = Todo.query.filter_by(id=todo_id, user_id=session['user_id']).first_or_404()
    t.done = not t.done
    db.session.commit()
    flash('وضعیت تسک تغییر کرد', 'success')
    return redirect(request.referrer or url_for('todo_list'))


if __name__ == "__main__":
    app.run(debug=True)
