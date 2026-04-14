import streamlit as st
import psycopg2
import random
import pandas as pd
from config import DB_CONFIG

# Настройка страницы
st.set_page_config(
    page_title="EnglishCard - Изучение английского",
    page_icon="📚",
    layout="wide"
)

# Инициализация состояния сессии
if 'user_id' not in st.session_state:
    st.session_state.user_id = 1
if 'current_word_id' not in st.session_state:
    st.session_state.current_word_id = None
if 'current_english' not in st.session_state:
    st.session_state.current_english = None
if 'current_russian' not in st.session_state:
    st.session_state.current_russian = None
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'last_answer_correct' not in st.session_state:
    st.session_state.last_answer_correct = None


# Функции работы с базой данных
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            username VARCHAR(100),
            registered_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS words (
            word_id SERIAL PRIMARY KEY,
            word_english VARCHAR(100) NOT NULL UNIQUE,
            word_russian VARCHAR(100) NOT NULL,
            category VARCHAR(50) DEFAULT 'common'
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_words (
            user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
            word_id INTEGER REFERENCES words(word_id) ON DELETE CASCADE,
            added_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (user_id, word_id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS statistics (
            user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
            word_id INTEGER REFERENCES words(word_id) ON DELETE CASCADE,
            correct_answers INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, word_id)
        )
    """)
    
    cur.execute("""
        INSERT INTO users (user_id, username)
        VALUES (1, 'default')
        ON CONFLICT (user_id) DO NOTHING
    """)
    
    initial_words = [
        ('red', 'красный', 'colors'),
        ('blue', 'синий', 'colors'),
        ('green', 'зелёный', 'colors'),
        ('yellow', 'жёлтый', 'colors'),
        ('black', 'чёрный', 'colors'),
        ('white', 'белый', 'colors'),
        ('cat', 'кот', 'animals'),
        ('dog', 'собака', 'animals'),
        ('sun', 'солнце', 'nature'),
        ('moon', 'луна', 'nature')
    ]
    
    for eng, rus, cat in initial_words:
        cur.execute("""
            INSERT INTO words (word_english, word_russian, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (word_english) DO NOTHING
        """, (eng, rus, cat))
    
    cur.execute("""
        INSERT INTO user_words (user_id, word_id)
        SELECT 1, word_id FROM words
        ON CONFLICT DO NOTHING
    """)
    
    conn.commit()
    cur.close()
    conn.close()


def get_user_words(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.word_id, w.word_english, w.word_russian
        FROM words w
        JOIN user_words uw ON w.word_id = uw.word_id
        WHERE uw.user_id = %s
        ORDER BY w.word_english
    """, (user_id,))
    words = cur.fetchall()
    cur.close()
    conn.close()
    return words


def add_user_word(user_id, english_word, russian_word):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO words (word_english, word_russian, category)
        VALUES (%s, %s, 'user_added')
        ON CONFLICT (word_english) DO UPDATE SET word_russian = EXCLUDED.word_russian
        RETURNING word_id
    """, (english_word.lower(), russian_word.lower()))
    
    word_id = cur.fetchone()[0]
    
    cur.execute("""
        INSERT INTO user_words (user_id, word_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
    """, (user_id, word_id))
    
    conn.commit()
    cur.close()
    conn.close()
    return word_id


def delete_user_word(user_id, word_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_words WHERE user_id = %s AND word_id = %s", (user_id, word_id))
    conn.commit()
    cur.close()
    conn.close()


def get_random_word_for_quiz(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.word_id, w.word_english, w.word_russian
        FROM words w
        JOIN user_words uw ON w.word_id = uw.word_id
        WHERE uw.user_id = %s
        ORDER BY RANDOM()
        LIMIT 1
    """, (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


def get_random_options(user_id, current_word_id, current_english):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.word_english FROM words w
        JOIN user_words uw ON w.word_id = uw.word_id
        WHERE uw.user_id = %s AND w.word_id != %s
        ORDER BY RANDOM()
        LIMIT 3
    """, (user_id, current_word_id))
    options = [row[0] for row in cur.fetchall()]
    
    if len(options) < 3:
        default_options = ['red', 'blue', 'green', 'yellow', 'black']
        for opt in default_options:
            if opt != current_english and opt not in options:
                options.append(opt)
            if len(options) == 3:
                break
    
    cur.close()
    conn.close()
    return options


def update_statistics(user_id, word_id, is_correct):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO statistics (user_id, word_id, correct_answers, total_attempts)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, word_id) DO UPDATE
        SET correct_answers = statistics.correct_answers + %s,
            total_attempts = statistics.total_attempts + 1
    """, (user_id, word_id, 1 if is_correct else 0, 1 if is_correct else 0))
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
        FROM statistics
        WHERE user_id = %s
    """, (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


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
init_db()


# Интерфейс приложения
st.title("EnglishCard - Изучение английского языка")
st.markdown("---")

# Боковая панель с навигацией
st.sidebar.title("Меню")
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
        Что ты можешь делать:
        - Изучать слова
        - Добавлять свои слова
        - Удалять слова
        - Смотреть статистику
        """)
    
    with col2:
        word_count = len(get_user_words(st.session_state.user_id))
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
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("Новое слово", use_container_width=True):
            st.session_state.current_word_id = None
            st.rerun()
    
    if st.session_state.current_word_id is None:
        word = get_random_word_for_quiz(st.session_state.user_id)
        if word:
            st.session_state.current_word_id = word[0]
            st.session_state.current_english = word[1]
            st.session_state.current_russian = word[2]
        else:
            st.warning("В вашем словаре нет слов. Добавьте новые слова.")
            st.stop()
    
    with col1:
        st.markdown(f"## Как переводится слово:")
        st.markdown(f"## {st.session_state.current_russian}")
    
    st.markdown("---")
    
    options = get_random_options(
        st.session_state.user_id,
        st.session_state.current_word_id,
        st.session_state.current_english
    )
    options.append(st.session_state.current_english)
    random.shuffle(options)
    
    cols = st.columns(2)
    for i, option in enumerate(options):
        col = cols[i % 2]
        if col.button(option, key=f"btn_{option}", use_container_width=True):
            is_correct = (option == st.session_state.current_english)
            update_statistics(st.session_state.user_id, st.session_state.current_word_id, is_correct)
            st.session_state.answer_submitted = True
            st.session_state.last_answer_correct = is_correct
    
    if st.session_state.answer_submitted:
        if st.session_state.last_answer_correct:
            st.success(f"Правильно. {st.session_state.current_english} - верный перевод.")
        else:
            st.error(f"Неправильно. Правильный ответ: {st.session_state.current_english}")
        
        if st.button("Следующее слово"):
            st.session_state.current_word_id = None
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
                add_user_word(st.session_state.user_id, english_word, russian_word)
                st.success(f"Слово {english_word} - {russian_word} добавлено")
            else:
                st.error("Заполните оба поля")
    
    st.markdown("---")
    st.subheader("Ваши слова")
    words = get_user_words(st.session_state.user_id)
    if words:
        df = pd.DataFrame(words, columns=['id', 'english', 'russian'])
        st.dataframe(df[['english', 'russian']], use_container_width=True)
    else:
        st.info("Словарь пуст. Добавьте свои первые слова")

# Удаление слова
elif page == "Удалить слово":
    st.header("Удалить слово")
    
    words = get_user_words(st.session_state.user_id)
    
    if words:
        word_dict = {f"{w[1]} - {w[2]}": w[0] for w in words}
        selected_word = st.selectbox("Выберите слово для удаления", list(word_dict.keys()))
        
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
            st.metric("Слов в словаре", len(get_user_words(st.session_state.user_id)))
        with col2:
            st.metric("Правильных ответов", stats[1])
        with col3:
            st.metric("Точность", f"{stats[2] or 0}%")
        
        st.markdown("---")
        st.subheader("Детальная статистика по словам")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT w.word_english, w.word_russian,
                   s.correct_answers, s.total_attempts,
                   ROUND(100.0 * s.correct_answers / NULLIF(s.total_attempts, 0), 1) as accuracy
            FROM statistics s
            JOIN words w ON s.word_id = w.word_id
            WHERE s.user_id = %s
            ORDER BY accuracy ASC
        """, (st.session_state.user_id,))
        
        data = cur.fetchall()
        cur.close()
        conn.close()
        
        if data:
            df = pd.DataFrame(data, columns=['Английский', 'Русский', 'Правильно', 'Всего', 'Точность'])
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
    2. words - словарь
    3. user_words - связь пользователей со словами
    4. statistics - статистика правильных ответов
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
    words -> user_words: один ко многим
    users -> statistics: один ко многим
    words -> statistics: один ко многим
    """)