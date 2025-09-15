# app.py
import streamlit as st
import openai
import sqlite3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import extra_streamlit_components as stx

# --- CONFIGURAÇÃO INICIAL ---
load_dotenv()
st.set_page_config(page_title="Meu ChatGPT Pessoal", page_icon="🤖", layout="wide")

# --- COOKIE MANAGER ---
cookies = stx.CookieManager()

# --- CHAVE OPENAI ---
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("Chave da API da OpenAI não encontrada! Configure a variável OPENAI_API_KEY.")
    st.stop()

# --- FUNÇÕES DE LOGIN ---
def show_login_page():
    st.title("Login")
    st.info("Esta é uma aplicação de uso pessoal.")

    CORRECT_USERNAME = os.getenv("LOGIN_USERNAME", "jorge")
    CORRECT_PASSWORD = os.getenv("LOGIN_PASSWORD", "dream2025@")

    username = st.text_input("Utilizador", key="username_input")
    password = st.text_input("Senha", type="password", key="password_input")

    if st.button("Entrar", key="login_button"):
        if username == CORRECT_USERNAME and password == CORRECT_PASSWORD:
            st.session_state.is_logged_in = True
            expires_at = datetime.now() + timedelta(hours=3)
            cookies.set("user_session", "logged_in", expires_at=expires_at)
            st.success("Login bem-sucedido!")
            st.rerun()
        else:
            st.error("Utilizador ou senha incorretos.")

# --- BANCO DE DADOS ---
DB_FILE = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'text',
            content TEXT NOT NULL,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    conn.commit()
    conn.close()

def get_conversations():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM conversations ORDER BY createdAt DESC")
    conversations = cursor.fetchall()
    conn.close()
    return conversations

def get_messages(conversation_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role, type, content FROM messages WHERE conversation_id = ? ORDER BY createdAt ASC", (conversation_id,))
    messages = cursor.fetchall()
    conn.close()
    return messages

def add_message(conversation_id, role, msg_type, content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (conversation_id, role, type, content) VALUES (?, ?, ?, ?)",
                   (conversation_id, role, msg_type, content))
    conn.commit()
    conn.close()

def create_conversation(title):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def delete_conversation(conversation_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()

def update_conversation_title(conversation_id, new_title):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conversation_id))
    conn.commit()
    conn.close()

init_db()

# --- ESTADO DE SESSÃO ---
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False

if not st.session_state.is_logged_in:
    session_cookie = cookies.get("user_session")
    if session_cookie == "logged_in":
        st.session_state.is_logged_in = True
    else:
        show_login_page()
        st.stop()

if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None
    st.session_state.messages = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("Histórico de Conversas")
    st.write("Bem-vindo!")

    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()

    conversations = get_conversations()
    for conv_id, conv_title in conversations:
        col1, col2 = st.columns([4,1])
        with col1:
            if st.button(conv_title, key=f"conv_{conv_id}", use_container_width=True):
                st.session_state.current_conversation_id = conv_id
                messages_from_db = get_messages(conv_id)
                st.session_state.messages = [{"role": r, "type": t, "content": c} for r, t, c in messages_from_db]
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{conv_id}", help="Apagar conversa"):
                delete_conversation(conv_id)
                if st.session_state.current_conversation_id == conv_id:
                    st.session_state.current_conversation_id = None
                    st.session_state.messages = []
                st.rerun()

    st.divider()
    if st.button("Sair (Logout)", use_container_width=True):
        st.session_state.is_logged_in = False
        cookies.delete("user_session")
        st.experimental_rerun()
        

# --- CHAT UI ---
st.title("🤖 Meu ChatGPT Pessoal")
st.caption("Um clone do ChatGPT para uso pessoal com Streamlit e Python")

tab_chat, tab_image, tab_audio = st.tabs(["💬 Chat", "🎨 Gerar Imagem", "🎤 Analisar Áudio"])

with tab_chat:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["type"] == "image_url":
                st.image(message["content"])
            else:
                st.markdown(message["content"])

    if prompt := st.chat_input("Em que posso ajudar?"):
        if st.session_state.current_conversation_id is None:
            new_id = create_conversation("Nova Conversa...")
            st.session_state.current_conversation_id = new_id

        st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        add_message(st.session_state.current_conversation_id, "user", "text", prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["type"]=="text"]

            try:
                # Streaming
                stream = openai.chat.completions.create(model="gpt-4o", messages=api_messages, stream=True)
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content is not None:
                        full_response += content
                        message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)
                add_message(st.session_state.current_conversation_id, "assistant", "text", full_response)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": full_response})
            except Exception as e:
                error_msg = f"Ocorreu um erro: {e}"
                st.error(error_msg)
                add_message(st.session_state.current_conversation_id, "assistant", "text", error_msg)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": error_msg})

with tab_image:
    st.header("🎨 Geração de Imagem com DALL-E 3")
    image_prompt = st.text_input("Descreva a imagem que você quer criar:")
    if st.button("Gerar Imagem"):
        if not image_prompt:
            st.warning("Por favor, descreva a imagem.")
        else:
            if st.session_state.current_conversation_id is None:
                new_id = create_conversation(f"Imagem: {image_prompt[:20]}...")
                st.session_state.current_conversation_id = new_id
                st.session_state.messages = []
            add_message(st.session_state.current_conversation_id, "user", "text", f"Gerar imagem: {image_prompt}")
            with st.spinner("A criar a sua imagem..."):
                try:
                    response = openai.images.generate(model="dall-e-3", prompt=image_prompt, n=1, size="1024x1024")
                    image_url = response.data[0].url
                    add_message(st.session_state.current_conversation_id, "assistant", "image_url", image_url)
                    st.image(image_url)
                    st.success("Imagem gerada!")
                except Exception as e:
                    st.error(f"Erro ao gerar imagem: {e}")

with tab_audio:
    st.header("🎤 Análise de Áudio com Whisper e GPT-4o")
    uploaded_file = st.file_uploader("Carregue um ficheiro de áudio (MP3, WAV, M4A...)", type=["mp3","wav","m4a","ogg"])
    if uploaded_file is not None:
        if st.session_state.current_conversation_id is None:
            new_id = create_conversation(f"Áudio: {uploaded_file.name}")
            st.session_state.current_conversation_id = new_id
            st.session_state.messages = []
        with st.spinner("A transcrever e analisar o áudio..."):
            try:
                transcription = openai.audio.transcriptions.create(model="whisper-1", file=uploaded_file)
                transcribed_text = transcription.text
                add_message(st.session_state.current_conversation_id, "user", "text", f"(Áudio): {transcribed_text}")
                completion = openai.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":transcribed_text}])
                assistant_response = completion.choices[0].message.content
                add_message(st.session_state.current_conversation_id, "assistant", "text", assistant_response)
                st.success("Áudio processado!")
                st.write(assistant_response)
            except Exception as e:
                st.error(f"Erro ao processar o áudio: {e}")
