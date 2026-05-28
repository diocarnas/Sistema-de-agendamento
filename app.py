from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from config import Config
from datetime import datetime
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
# Carrega as configurações do arquivo config.py que criamos acima
app.config.from_object(Config)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info"

# --- TIPOS DE QUADRA DISPONÍVEIS ---
COURT_TYPES = [
    ('society',      'Society'),
    ('volei',        'Vôlei'),
    ('futsal',       'Futsal'),
    ('quadra_areia', 'Quadra de Areia'),
    ('campo',        'Campo'),
]

# --- MODELOS ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    bookings = db.relationship('Booking', backref='author', lazy=True, cascade="all, delete-orphan")

class Court(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    # court_type deve conter um dos valores da chave em COURT_TYPES
    # ex: 'society', 'volei', 'futsal', 'quadra_areia', 'campo'
    court_type = db.Column(db.String(30), nullable=False, index=True)
    bookings = db.relationship('Booking', backref='court', lazy=True)

    @property
    def court_type_label(self):
        """Retorna o rótulo legível do tipo de quadra."""
        return dict(COURT_TYPES).get(self.court_type, self.court_type)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    # Aumentado para 20 para evitar erros de limite estrito no MySQL
    time_slot = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    court_id = db.Column(db.Integer, db.ForeignKey('court.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ROTAS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password')

        if not username or not email or not password:
            flash('Preencha todos os campos!', 'warning')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Conta criada com sucesso! Faça seu login.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('Usuário ou E-mail já cadastrado.', 'danger')
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Falha no login. Verifique suas credenciais.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Lê o filtro de tipo de quadra da query string (?court_type=...)
    selected_type = request.args.get('court_type', '')

    # Filtra as quadras pelo tipo, ou retorna todas se nenhum tipo for selecionado
    valid_types = [key for key, _ in COURT_TYPES]
    if selected_type and selected_type in valid_types:
        courts = Court.query.filter_by(court_type=selected_type).all()
    else:
        selected_type = ''
        courts = Court.query.all()

    user_bookings = (
        Booking.query
        .filter_by(user_id=current_user.id)
        .order_by(Booking.date.asc())
        .all()
    )

    return render_template(
        'dashboard.html',
        courts=courts,
        bookings=user_bookings,
        court_types=COURT_TYPES,       # lista completa para montar os botões/filtro
        selected_type=selected_type,   # tipo atualmente selecionado
    )

@app.route('/api/courts')
@login_required
def api_courts():
    """
    Endpoint JSON para filtrar quadras por tipo dinamicamente (AJAX).
    Uso: GET /api/courts?court_type=futsal
    Retorna: [{"id": 1, "name": "Quadra A", "court_type": "futsal", "court_type_label": "Futsal"}, ...]
    """
    court_type = request.args.get('court_type', '')
    valid_types = [key for key, _ in COURT_TYPES]

    query = Court.query
    if court_type and court_type in valid_types:
        query = query.filter_by(court_type=court_type)

    courts = query.all()
    return jsonify([
        {
            'id': c.id,
            'name': c.name,
            'court_type': c.court_type,
            'court_type_label': c.court_type_label,
        }
        for c in courts
    ])

@app.route('/book', methods=['POST'])
@login_required
def book():
    try:
        date_str = request.form.get('date')
        time_slot = request.form.get('time_slot')
        court_id = request.form.get('court_id')
        
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # 1. Impedir agendamento no passado
        if booking_date < datetime.today().date():
            flash('Não é possível agendar para uma data passada.', 'warning')
            return redirect(url_for('dashboard'))

        # 2. Verificar conflito
        conflict = Booking.query.filter_by(
            date=booking_date, 
            time_slot=time_slot, 
            court_id=court_id
        ).first()
        
        if conflict:
            flash('Este horário já está reservado por outra pessoa.', 'danger')
        else:
            new_booking = Booking(
                date=booking_date, 
                time_slot=time_slot, 
                court_id=court_id, 
                user_id=current_user.id
            )
            db.session.add(new_booking)
            db.session.commit()
            flash('Agendamento confirmado!', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash('Erro ao processar agendamento. Tente novamente.', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = db.session.get(Booking, booking_id)

    # Garante que só o dono pode cancelar
    if not booking or booking.user_id != current_user.id:
        flash('Agendamento não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        db.session.delete(booking)
        db.session.commit()
        flash('Agendamento cancelado com sucesso.', 'success')
    except Exception:
        db.session.rollback()
        flash('Erro ao cancelar agendamento. Tente novamente.', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # O bloco abaixo garante que, ao rodar o app, o SQLAlchemy crie as 
    # tabelas automaticamente caso elas não existam no MySQL.
    with app.app_context():
        db.create_all()
    app.run(debug=True)