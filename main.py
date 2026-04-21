import streamlit as st
import psycopg2
import random
import pandas as pd
from config import DB_CONFIG

# Настройка страницы
st.set_page_config(
    page_title="EnglishCard - Изучение английского",
    layout="wide"
)

# Инициализация состояния сессии
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'current_word' not in st.session_state:
    st.session_state.current_word = None
if 'current_word_id' not in st.session_state:
    st.session_state.current_word_id = None
if 'current_word_type' not in st.session_state:
    st.session_state.current_word_type = None
if 'current_english' not in st.session_state:
    st.session_state.current_english = None
if 'current_russian' not in st.session_state:
    st.session_state.current_russian = None
if 'options' not in st.session_state:
    st.session_state.options = []
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'last_answer_correct' not in st.session_state:
    st.session_state.last_answer_correct = None
if 'login_form' not in st.session_state:
    st.session_state.login_form = 'login'


# Функции работы с базой данных
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def init_database():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS common_words (
            id SERIAL PRIMARY KEY,
            russian_word VARCHAR(100) NOT NULL,
            english_word VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_words (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            russian_word VARCHAR(100) NOT NULL,
            english_word VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS learning_stats (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            word_id INTEGER NOT NULL,
            word_type VARCHAR(20) NOT NULL,
            correct_answers INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            last_reviewed TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("SELECT COUNT(*) FROM common_words")
    count = cur.fetchone()[0]

    if count == 0:
        initial_words = [
            ('красный', 'red'),
            ('синий', 'blue'),
            ('зелёный', 'green'),
            ('жёлтый', 'yellow'),
            ('чёрный', 'black'),
            ('белый', 'white'),
            ('оранжевый', 'orange'),
            ('фиолетовый', 'purple'),
            ('розовый', 'pink'),
            ('коричневый', 'brown'),
            ('кот', 'cat'),
            ('собака', 'dog'),
            ('мышь', 'mouse'),
            ('птица', 'bird'),
            ('рыба', 'fish'),
            ('лошадь', 'horse'),
            ('корова', 'cow'),
            ('свинья', 'pig'),
            ('медведь', 'bear'),
            ('волк', 'wolf'),
            ('солнце', 'sun'),
            ('луна', 'moon'),
            ('звезда', 'star'),
            ('небо', 'sky'),
            ('облако', 'cloud'),
            ('дождь', 'rain'),
            ('снег', 'snow'),
            ('ветер', 'wind'),
            ('дерево', 'tree'),
            ('цветок', 'flower'),
            ('машина', 'car'),
            ('дом', 'house'),
            ('вода', 'water'),
            ('огонь', 'fire'),
            ('хлеб', 'bread'),
            ('молоко', 'milk'),
            ('яблоко', 'apple'),
            ('стул', 'chair'),
            ('стол', 'table'),
            ('книга', 'book')
        ]

        for rus, eng in initial_words:
            cur.execute("""
                INSERT INTO common_words (russian_word, english_word)
                VALUES (%s, %s)
            """, (rus, eng))

    conn.commit()
    cur.close()
    conn.close()


def register_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (username, password)
            VALUES (%s, %s)
            RETURNING id
        """, (username, password))
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    except psycopg2.Error:
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def login_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM users
        WHERE username = %s AND password = %s
    """, (username, password))

    result = cur.fetchone()
    cur.close()
    conn.close()

    if result:
        return result[0]
    return None


def get_user_words_count(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT id FROM common_words
            UNION
            SELECT id FROM user_words WHERE user_id = %s
        ) AS all_words
    """, (user_id,))

    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_quiz_words(user_id):
    """
    Возвращает 4 случайных слова (общие + персональные) за один запрос.
    Первое слово используется как основное, остальные как варианты ответа.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM (
            SELECT id, russian_word, english_word, 'common' as word_type
            FROM common_words
            UNION
            SELECT id, russian_word, english_word, 'user' as word_type
            FROM user_words
            WHERE user_id = %s
        ) AS all_words
        ORDER BY RANDOM()
        LIMIT 4
    """, (user_id,))

    result = cur.fetchall()
    cur.close()
    conn.close()
    return result


def add_user_word(user_id, russian_word, english_word):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO user_words (user_id, russian_word, english_word)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (user_id, russian_word, english_word))

    word_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return word_id


def delete_user_word(user_id, word_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM user_words
        WHERE user_id = %s AND id = %s
    """, (user_id, word_id))

    conn.commit()
    cur.close()
    conn.close()


def get_user_words_list(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, russian_word, english_word
        FROM user_words
        WHERE user_id = %s
        ORDER BY english_word
    """, (user_id,))

    words = cur.fetchall()
    cur.close()
    conn.close()
    return words


def update_statistics(user_id, word_id, word_type, is_correct):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM learning_stats
        WHERE user_id = %s AND word_id = %s AND word_type = %s
    """, (user_id, word_id, word_type))

    exists = cur.fetchone()

    if exists:
        cur.execute("""
            UPDATE learning_stats
            SET correct_answers = correct_answers + %s,
                total_attempts = total_attempts + 1,
                last_reviewed = NOW()
            WHERE user_id = %s AND word_id = %s AND word_type = %s
        """, (1 if is_correct else 0, user_id, word_id, word_type))
    else:
        cur.execute("""
            INSERT INTO learning_stats (user_id, word_id, word_type, correct_answers, total_attempts)
            VALUES (%s, %s, %s, %s, 1)
        """, (user_id, word_id, word_type, 1 if is_correct else 0))

    conn.commit()
    cur.close()
    conn.close()


def get_statistics(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            SUM(total_attempts) as total_attempts,
            SUM(correct_answers) as correct_answers,
            ROUND(100.0 * SUM(correct_answers) / NULLIF(SUM(total_attempts), 0), 1) as accuracy
        FROM learning_stats
        WHERE user_id = %s
    """, (user_id,))

    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


def get_detailed_statistics(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            CASE WHEN ls.word_type = 'common' THEN cw.russian_word ELSE uw.russian_word END as russian_word,
            CASE WHEN ls.word_type = 'common' THEN cw.english_word ELSE uw.english_word END as english_word,
            ls.correct_answers,
            ls.total_attempts,
            ROUND(100.0 * ls.correct_answers / NULLIF(ls.total_attempts, 0), 1) as accuracy
        FROM learning_stats ls
        LEFT JOIN common_words cw ON ls.word_id = cw.id AND ls.word_type = 'common'
        LEFT JOIN user_words uw ON ls.word_id = uw.id AND ls.word_type = 'user'
        WHERE ls.user_id = %s
        ORDER BY accuracy ASC
    """, (user_id,))

    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


def get_schema_info():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """)

    schema = {}
    for table, column, dtype in cur.fetchall():
        if table not in schema:
            schema[table] = []
        schema[table].append(f"{column} ({dtype})")

    cur.close()
    conn.close()
    return schema


# Инициализация базы данных
init_database()


# Функции авторизации
def show_login_form():
    st.header("Вход в систему")

    with st.form("login"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")

        if submitted:
            if username and password:
                user_id = login_user(username, password)
                if user_id:
                    st.session_state.user_id = user_id
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль")
            else:
                st.error("Заполните все поля")

    st.markdown("---")

    if st.button("Зарегистрироваться"):
        st.session_state.login_form = 'register'
        st.rerun()


def show_register_form():
    st.header("Регистрация")

    with st.form("register"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        confirm_password = st.text_input("Подтвердите пароль", type="password")
        submitted = st.form_submit_button("Зарегистрироваться")

        if submitted:
            if username and password and confirm_password:
                if password != confirm_password:
                    st.error("Пароли не совпадают")
                else:
                    user_id = register_user(username, password)
                    if user_id:
                        st.success("Регистрация прошла успешно")
                        st.session_state.user_id = user_id
                        st.rerun()
                    else:
                        st.error("Пользователь с таким логином уже существует")
            else:
                st.error("Заполните все поля")

    st.markdown("---")

    if st.button("Войти"):
        st.session_state.login_form = 'login'
        st.rerun()


# Интерфейс приложения
def main_app():
    st.title("EnglishCard - Изучение английского языка")
    st.markdown("---")

    st.sidebar.title("Меню")
    st.sidebar.write(f"Вы вошли как пользователь ID: {st.session_state.user_id}")

    if st.sidebar.button("Выйти"):
        st.session_state.user_id = None
        st.session_state.login_form = 'login'
        st.rerun()

    page = st.sidebar.radio(
        "Выберите раздел",
        ["Главная", "Изучение", "Добавить слово", "Удалить слово", "Статистика", "Схема БД"]
    )

    # Главная страница
    if page == "Главная":
        st.header("Добро пожаловать в EnglishCard")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            Что вы можете делать:
            - Изучать слова
            - Добавлять свои слова
            - Удалять слова
            - Смотреть статистику
            """)

        with col2:
            word_count = get_user_words_count(st.session_state.user_id)
            stats = get_statistics(st.session_state.user_id)

            st.metric("Слов в словаре", word_count)
            if stats and stats[1]:
                st.metric("Правильных ответов", stats[1])
                st.metric("Точность", f"{stats[2] or 0}%")
            else:
                st.info("Пройдите первый тест, чтобы увидеть статистику")

    # Изучение
    elif page == "Изучение":
        st.header("Изучение слов")

        # Кнопка нового слова
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Новое слово", use_container_width=True):
                st.session_state.current_word = None
                st.session_state.answer_submitted = False
                st.rerun()

        # Загружаем 4 слова за один запрос
        if st.session_state.current_word is None:
            words = get_quiz_words(st.session_state.user_id)
            if words and len(words) >= 4:
                # Сохраняем все 4 слова
                st.session_state.current_word = words
                # Первое слово используем как основное
                st.session_state.current_word_id = words[0][0]
                st.session_state.current_russian = words[0][1]
                st.session_state.current_english = words[0][2]
                st.session_state.current_word_type = words[0][3]
                # Варианты ответа - все 4 слова, перемешиваем
                options = [w[2] for w in words]
                random.shuffle(options)
                st.session_state.options = options
            else:
                st.warning("В вашем словаре недостаточно слов. Добавьте новые слова.")
                st.stop()

        # Отображаем вопрос
        with col1:
            st.markdown(f"## Как переводится слово:")
            st.markdown(f"## {st.session_state.current_russian}")

        st.markdown("---")

        correct_answer = st.session_state.current_english
        options = st.session_state.options
        disabled = st.session_state.answer_submitted

        # Отображаем кнопки с вариантами
        cols = st.columns(2)
        for i, option in enumerate(options):
            col = cols[i % 2]
            if col.button(option, key=f"quiz_btn_{i}", use_container_width=True, disabled=disabled):
                # Определяем правильность ответа
                is_correct = (option == correct_answer)
                
                # Обновляем состояние и статистику без дублирования
                st.session_state.last_answer_correct = is_correct
                update_statistics(
                    st.session_state.user_id,
                    st.session_state.current_word_id,
                    st.session_state.current_word_type,
                    is_correct
                )
                st.session_state.answer_submitted = True

        # Показываем результат после ответа
        if st.session_state.answer_submitted:
            if st.session_state.last_answer_correct:
                st.success(f"Правильно. {correct_answer} - верный перевод.")
            else:
                st.error(f"Неправильно. Правильный ответ: {correct_answer}")

            if st.button("Следующее слово"):
                st.session_state.current_word = None
                st.session_state.answer_submitted = False
                st.rerun()

    # Добавление слова
    elif page == "Добавить слово":
        st.header("Добавить новое слово")

        with st.form("add_word_form"):
            col1, col2 = st.columns(2)
            with col1:
                english_word = st.text_input("Слово на английском")
            with col2:
                russian_word = st.text_input("Перевод на русский")

            submitted = st.form_submit_button("Добавить слово", use_container_width=True)

            if submitted:
                if english_word and russian_word:
                    add_user_word(st.session_state.user_id, russian_word, english_word)
                    st.success(f"Слово {english_word} - {russian_word} добавлено")
                    st.rerun()
                else:
                    st.error("Заполните оба поля")

        st.markdown("---")
        st.subheader("Ваши слова")

        words = get_user_words_list(st.session_state.user_id)
        if words:
            df = pd.DataFrame(words, columns=['id', 'russian', 'english'])
            st.dataframe(df[['english', 'russian']], use_container_width=True)
        else:
            st.info("Словарь пуст. Добавьте свои первые слова")

    # Удаление слова
    elif page == "Удалить слово":
        st.header("Удалить слово")

        words = get_user_words_list(st.session_state.user_id)

        if words:
            word_dict = {f"{w[2]} - {w[1]}": w[0] for w in words}
            selected_word = st.selectbox("Выберите слово для удаления", list(word_dict.keys()), key="delete_select")
            if st.button("Удалить", use_container_width=True):
                word_id = word_dict[selected_word]
                delete_user_word(st.session_state.user_id, word_id)
                st.success(f"Слово {selected_word} удалено")
                st.rerun()
        else:
            st.info("Словарь пуст. Добавьте слова перед удалением")

    # Статистика
    elif page == "Статистика":
        st.header("Статистика")

        stats = get_statistics(st.session_state.user_id)

        if stats and stats[1]:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Слов в словаре", get_user_words_count(st.session_state.user_id))
            with col2:
                st.metric("Правильных ответов", stats[1])
            with col3:
                st.metric("Точность", f"{stats[2] or 0}%")

            st.markdown("---")
            st.subheader("Детальная статистика по словам")

            data = get_detailed_statistics(st.session_state.user_id)

            if data:
                df = pd.DataFrame(data, columns=['Русский', 'Английский', 'Правильно', 'Всего', 'Точность'])
                st.dataframe(df, use_container_width=True)
        else:
            st.info("Статистики пока нет. Пройдите первый тест в разделе Изучение")

    # Схема БД
    elif page == "Схема БД":
        st.header("Схема базы данных")

        st.markdown("""
        Структура базы данных EnglishCard

        База данных состоит из 4 таблиц:

        1. users - пользователи
        2. common_words - общие слова
        3. user_words - пользовательские слова
        4. learning_stats - статистика обучения
        """)

        schema = get_schema_info()

        for table, columns in schema.items():
            with st.expander(f"Таблица: {table}"):
                for col in columns:
                    st.text(f"  {col}")

        st.markdown("---")
        st.markdown("### Связи между таблицами")
        st.markdown("""
        users -> user_words: один ко многим
        users -> learning_stats: один ко многим
        common_words -> learning_stats: один ко многим
        user_words -> learning_stats: один ко многим
        """)


# Основной поток
if st.session_state.user_id is None:
    if st.session_state.login_form == 'login':
        show_login_form()
    else:
        show_register_form()
else:
    main_app()