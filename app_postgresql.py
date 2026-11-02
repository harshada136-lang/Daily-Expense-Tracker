from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date, timedelta
import os, hashlib, re
import psycopg2
from psycopg2.extras import DictCursor

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_URL = os.environ.get('DATABASE_URL')
app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get('SECRET_KEY', 'dets-local-change-this-key')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


# Serve frontend assets from the repository root.
# The CSS, JS, fonts and image folders are currently at the repository root,
# rather than inside a "static" folder.
@app.route('/static/<path:filename>', endpoint='static')
def serve_static(filename):
    allowed_dirs = {
        'css', 'js', 'fonts', 'bootstrap', 'flot',
        'flot.tooltip', 'gmaps', 'images', 'jquery',
        'sticky-kit-master', 'styleswitcher'
    }

    first_folder = filename.split('/', 1)[0]
    if first_folder not in allowed_dirs:
        abort(404)

    return send_from_directory(BASE_DIR, filename)



class DBConnection:
    """Small compatibility wrapper so existing app queries can use ? placeholders."""
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        cursor = self.connection.cursor()
        query = query.replace("?", "%s")
        cursor.execute(query, params or ())
        return cursor

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Add the Neon connection string in Render Environment.")
    connection = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    return DBConnection(connection)


def init_db():
    con = get_db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS tbluser (
            ID BIGSERIAL PRIMARY KEY,
            FullName TEXT NOT NULL,
            Email TEXT NOT NULL UNIQUE,
            MobileNumber TEXT,
            Password TEXT NOT NULL,
            RegDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tblexpense (
            ID BIGSERIAL PRIMARY KEY,
            UserId BIGINT NOT NULL REFERENCES tbluser(ID) ON DELETE CASCADE,
            ExpenseDate DATE NOT NULL,
            ExpenseItem TEXT NOT NULL,
            ExpenseCost DOUBLE PRECISION NOT NULL,
            NoteDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_expense_user_date ON tblexpense(UserId, ExpenseDate)")
    con.commit()
    con.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('uid'):
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def password_matches(stored, supplied):
    if not stored:
        return False
    if stored.startswith(('scrypt:', 'pbkdf2:')):
        return check_password_hash(stored, supplied)
    return hashlib.md5(supplied.encode('utf-8')).hexdigest() == stored


def current_user():
    uid = session.get('uid')
    if not uid:
        return None
    con = get_db()
    user = con.execute('SELECT * FROM tbluser WHERE ID=?', (uid,)).fetchone()
    con.close()
    return user


@app.context_processor
def inject_globals():
    return {'current_user': current_user(), 'today_iso': date.today().isoformat()}


@app.route('/', methods=['GET', 'POST'])
@app.route('/index.php', methods=['GET', 'POST'])
def login():
    if session.get('uid'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        con = get_db()
        user = con.execute('SELECT ID, Password FROM tbluser WHERE lower(Email)=?', (email,)).fetchone()
        if user and password_matches(user['Password'], password):
            # Upgrade legacy MD5 hashes after successful login.
            if not user['Password'].startswith(('scrypt:', 'pbkdf2:')):
                con.execute('UPDATE tbluser SET Password=? WHERE ID=?', (generate_password_hash(password), user['ID']))
                con.commit()
            session.clear()
            session['uid'] = user['ID']
            con.close()
            return redirect(url_for('dashboard'))
        con.close()
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', page_title='Login')


@app.route('/register.php', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('mobilenumber', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('repeatpassword', '')
        if not name or not email or not password:
            flash('Please complete all required fields.', 'danger')
        elif not re.fullmatch(r'\d{10}', mobile):
            flash('Enter a valid 10-digit mobile number.', 'danger')
        elif password != confirm:
            flash('Password and confirm password do not match.', 'danger')
        elif len(password) < 6:
            flash('Password must contain at least 6 characters.', 'danger')
        else:
            con = get_db()
            try:
                con.execute('INSERT INTO tbluser(FullName,Email,MobileNumber,Password) VALUES(?,?,?,?)',
                            (name, email, mobile, generate_password_hash(password)))
                con.commit()
                flash('Registration successful. Please login.', 'success')
                con.close()
                return redirect(url_for('login'))
            except psycopg2.IntegrityError:
                con.close()
                flash('This email is already registered.', 'danger')
    return render_template('register.html', page_title='Register')


@app.route('/logout.php')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard.php')
@login_required
def dashboard():
    today = date.today()
    periods = {
        'today': (today.isoformat(), today.isoformat()),
        'yesterday': ((today-timedelta(days=1)).isoformat(), (today-timedelta(days=1)).isoformat()),
        'week': ((today-timedelta(days=6)).isoformat(), today.isoformat()),
        'month': (today.replace(day=1).isoformat(), today.isoformat()),
        'year': (today.replace(month=1, day=1).isoformat(), today.isoformat()),
    }
    con = get_db()
    sums = {}
    for key, (start, end) in periods.items():
        sums[key] = con.execute('SELECT COALESCE(SUM(CAST(ExpenseCost AS REAL)),0) FROM tblexpense WHERE UserId=? AND ExpenseDate BETWEEN ? AND ?',
                                (session['uid'], start, end)).fetchone()[0]
    total = con.execute('SELECT COALESCE(SUM(CAST(ExpenseCost AS REAL)),0) FROM tblexpense WHERE UserId=?', (session['uid'],)).fetchone()[0]
    sums['total'] = total
    recent = con.execute('SELECT * FROM tblexpense WHERE UserId=? ORDER BY ExpenseDate DESC, ID DESC LIMIT 8', (session['uid'],)).fetchall()
    con.close()
    return render_template('dashboard.html', page_title='Dashboard', sums=sums, recent=recent)


@app.route('/add-expense.php', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        expense_date = request.form.get('dateexpense', '')
        item = request.form.get('item', '').strip()
        try:
            cost = float(request.form.get('costitem', '').replace(',', ''))
            date.fromisoformat(expense_date)
            if not item or cost <= 0:
                raise ValueError
            con = get_db()
            con.execute('INSERT INTO tblexpense(UserId,ExpenseDate,ExpenseItem,ExpenseCost) VALUES(?,?,?,?)',
                        (session['uid'], expense_date, item, cost))
            con.commit(); con.close()
            flash('Expense has been added successfully.', 'success')
            return redirect(url_for('manage_expense'))
        except (ValueError, TypeError):
            flash('Enter a valid date, item and positive expense amount.', 'danger')
    return render_template('add_expense.html', page_title='Add Expense')


@app.route('/manage-expense.php', methods=['GET', 'POST'])
@login_required
def manage_expense():
    con = get_db()
    delid = request.form.get('delid') if request.method == 'POST' else request.args.get('delid')
    if delid:
        con.execute('DELETE FROM tblexpense WHERE ID=? AND UserId=?', (delid, session['uid']))
        con.commit()
        flash('Expense record deleted.', 'success')
    rows = con.execute('SELECT * FROM tblexpense WHERE UserId=? ORDER BY ExpenseDate DESC, ID DESC', (session['uid'],)).fetchall()
    con.close()
    return render_template('manage_expense.html', page_title='Manage Expense', rows=rows)


@app.route('/user-profile.php', methods=['GET', 'POST'])
@login_required
def profile():
    con = get_db()
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('contactnumber', '').strip()
        if not fullname or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or not re.fullmatch(r'\d{10}', mobile):
            flash('Enter a valid name, email address and 10-digit mobile number.', 'danger')
        else:
            existing = con.execute('SELECT ID FROM tbluser WHERE lower(Email)=lower(?) AND ID<>?', (email, session['uid'])).fetchone()
            if existing:
                flash('This email address is already registered to another account.', 'danger')
            else:
                con.execute('UPDATE tbluser SET FullName=?, Email=?, MobileNumber=? WHERE ID=?', (fullname, email, mobile, session['uid']))
                con.commit()
                flash('Profile updated successfully.', 'success')
    user = con.execute('SELECT * FROM tbluser WHERE ID=?', (session['uid'],)).fetchone()
    con.close()
    return render_template('profile.html', page_title='User Profile', user=user)


@app.route('/change-password.php', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old = request.form.get('currentpassword', '')
        new = request.form.get('newpassword', '')
        confirm = request.form.get('confirmpassword', '')
        con = get_db(); user = con.execute('SELECT Password FROM tbluser WHERE ID=?', (session['uid'],)).fetchone()
        if not user or not password_matches(user['Password'], old):
            flash('Current password is incorrect.', 'danger')
        elif len(new) < 6:
            flash('New password must contain at least 6 characters.', 'danger')
        elif new != confirm:
            flash('New password and confirmation do not match.', 'danger')
        else:
            con.execute('UPDATE tbluser SET Password=? WHERE ID=?', (generate_password_hash(new), session['uid']))
            con.commit(); flash('Password changed successfully.', 'success')
        con.close()
    return render_template('change_password.html', page_title='Change Password')


@app.route('/forgot-password.php', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        mobile = request.form.get('contactno', '').strip()
        con = get_db(); user = con.execute('SELECT ID FROM tbluser WHERE lower(Email)=? AND MobileNumber=?', (email, mobile)).fetchone(); con.close()
        if user:
            session['reset_uid'] = user['ID']
            return redirect(url_for('reset_password'))
        flash('Email and mobile number do not match.', 'danger')
    return render_template('forgot.html', page_title='Forgot Password')


@app.route('/reset-password.php', methods=['GET', 'POST'])
def reset_password():
    if not session.get('reset_uid'):
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        new = request.form.get('newpassword', '')
        confirm = request.form.get('confirmpassword', '')
        if len(new) < 6:
            flash('Password must contain at least 6 characters.', 'danger')
        elif new != confirm:
            flash('Password and confirmation do not match.', 'danger')
        else:
            con = get_db(); con.execute('UPDATE tbluser SET Password=? WHERE ID=?', (generate_password_hash(new), session.pop('reset_uid'))); con.commit(); con.close()
            flash('Password reset successfully. Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('reset.html', page_title='Reset Password')


REPORTS = {
    'expense-datewise-reports': ('Daywise Expenses', 'day'),
    'expense-monthwise-reports': ('Monthwise Expenses', 'month'),
    'expense-yearwise-reports': ('Yearwise Expenses', 'year'),
    'expense-reports': ('Expense Reports', 'all'),
}

@app.route('/<report>.php', methods=['GET', 'POST'])
@login_required
def reports(report):
    if report not in REPORTS:
        abort(404)
    title, grouping = REPORTS[report]
    start = request.values.get('fromdate', '')
    end = request.values.get('todate', '')
    rows = []; total = 0.0
    con = get_db()
    if start and end:
        try:
            date.fromisoformat(start); date.fromisoformat(end)
            if start > end:
                flash('From date cannot be later than To date.', 'danger')
            else:
                if grouping == 'all':
                    rows = con.execute('SELECT * FROM tblexpense WHERE UserId=? AND ExpenseDate BETWEEN ? AND ? ORDER BY ExpenseDate DESC, ID DESC', (session['uid'], start, end)).fetchall()
                else:
                    fmt = {'day': 'substr(ExpenseDate::text,1,10)', 'month': "substr(ExpenseDate::text,1,7)", 'year': 'substr(ExpenseDate::text,1,4)'}[grouping]
                    rows = con.execute(f'SELECT {fmt} AS Period, SUM(CAST(ExpenseCost AS REAL)) AS Amount, COUNT(*) AS Entries FROM tblexpense WHERE UserId=? AND ExpenseDate BETWEEN ? AND ? GROUP BY Period ORDER BY Period DESC', (session['uid'], start, end)).fetchall()
                total = sum(float(r['ExpenseCost'] if grouping == 'all' else r['Amount'] or 0) for r in rows)
        except ValueError:
            flash('Please select valid dates.', 'danger')
    con.close()
    return render_template('reports.html', page_title=title, title=title, report=report, grouping=grouping, rows=rows, total=total, start=start, end=end)


@app.route('/<path:unused>')
def fallback(unused):
    return redirect(url_for('dashboard') if session.get('uid') else url_for('login'))


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)
