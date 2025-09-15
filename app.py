# app.py
import streamlit as st
import openai
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
# --- CONFIGURAÇÃO INICIAL ---

# Configura o título da página, layout, etc.
st.set_page_config(
    page_title="Meu ChatGPT Pessoal",
    page_icon="🤖",
    layout="wide"
)

load_dotenv() 

 # Carrega variáveis de ambiente do ficheiro .env



# Usa a chave da API da variável de ambiente
try:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    # Testa a chave para garantir que está a funcionar
    if not openai.api_key:
        st.error("Chave da API da OpenAI não encontrada! Por favor, configure a variável de ambiente OPENAI_API_KEY.")
        st.stop()
except Exception as e:
    st.error(f"Erro ao configurar a API da OpenAI: {e}")
    st.stop()

# --- GESTÃO DA BASE DE DADOS (SQLITE) ---

def init_db():
    """Inicializa a base de dados e cria as tabelas se não existirem."""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    # Tabela de conversas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Tabela de mensagens
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
    """Busca todas as conversas da base de dados."""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM conversations ORDER BY createdAt DESC")
    conversations = cursor.fetchall()
    conn.close()
    return conversations

def get_messages(conversation_id):
    """Busca todas as mensagens de uma conversa específica."""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute("SELECT role, type, content FROM messages WHERE conversation_id = ? ORDER BY createdAt ASC", (conversation_id,))
    messages = cursor.fetchall()
    conn.close()
    return messages

def add_message(conversation_id, role, msg_type, content):
    """Adiciona uma nova mensagem à base de dados."""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (conversation_id, role, type, content) VALUES (?, ?, ?, ?)",
                   (conversation_id, role, msg_type, content))
    conn.commit()
    conn.close()

def create_conversation(title):
    """Cria uma nova conversa e retorna o seu ID."""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def delete_conversation(conversation_id):
    """Apaga uma conversa e todas as suas mensagens."""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()

def update_conversation_title(conversation_id, new_title):
    """Atualiza o título de uma conversa."""
    conn = sqlite3.connect('chat_history.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conversation_id))
    conn.commit()
    conn.close()

# Inicializa a base de dados na primeira execução
init_db()

# --- LÓGICA DA APLICAÇÃO STREAMLIT ---

# Inicialização do estado da sessão
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None
    st.session_state.messages = []

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.title("Histórico de Conversas")

    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()

    conversations = get_conversations()
    for conv_id, conv_title in conversations:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(conv_title, key=f"conv_{conv_id}", use_container_width=True):
                st.session_state.current_conversation_id = conv_id
                # Carrega as mensagens da conversa selecionada
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

# --- INTERFACE PRINCIPAL DO CHAT ---

st.title("🤖 Meu ChatGPT Pessoal")
st.caption("Um clone do ChatGPT para uso pessoal com Streamlit e Python")

# Tabs para diferentes modos de interação
tab_chat, tab_image, tab_audio = st.tabs(["💬 Chat", "🎨 Gerar Imagem", "🎤 Analisar Áudio"])

# --- TAB DE CHAT ---
with tab_chat:
    # Exibe as mensagens da conversa atual
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["type"] == "image_url":
                st.image(message["content"])
            else:
                st.markdown(message["content"])

    # Input do utilizador
    if prompt := st.chat_input("Em que posso ajudar?"):
        # Se for uma nova conversa, cria-a primeiro
        if st.session_state.current_conversation_id is None:
            new_id = create_conversation("Nova Conversa...")
            st.session_state.current_conversation_id = new_id

        # Adiciona a mensagem do user à UI e à DB
        st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        add_message(st.session_state.current_conversation_id, "user", "text", prompt)

        # Prepara para a resposta do assistente (stream)
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Formata as mensagens para a API
            api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["type"] == "text"]

            try:
                # Chama a API da OpenAI em modo stream
                stream = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=api_messages,
                    stream=True,
                )
                # Itera sobre os chunks da resposta
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content is not None:
                        full_response += content
                        message_placeholder.markdown(full_response + "▌") # Mostra um cursor a piscar
                message_placeholder.markdown(full_response)
                
                # Guarda a resposta completa na DB e no estado
                add_message(st.session_state.current_conversation_id, "assistant", "text", full_response)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": full_response})

                # Se for a primeira mensagem, gera um título para a conversa
                if len(api_messages) <= 2: # User + Assistant
                    title_prompt = f"Gere um título curto (máximo 5 palavras) para a seguinte conversa: User: {prompt}\nAssistant: {full_response}"
                    title_response = openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": title_prompt}]
                    )
                    new_title = title_response.choices[0].message.content.strip().replace('"', '')
                    update_conversation_title(st.session_state.current_conversation_id, new_title)
                    st.rerun()

            except Exception as e:
                error_message = f"Ocorreu um erro: {e}"
                st.error(error_message)
                add_message(st.session_state.current_conversation_id, "assistant", "text", error_message)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": error_message})


# --- TAB DE GERAÇÃO DE IMAGEM ---
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
                    response = openai.images.generate(
                        model="dall-e-3",
                        prompt=image_prompt,
                        n=1,
                        size="1024x1024"
                    )
                    image_url = response.data[0].url
                    add_message(st.session_state.current_conversation_id, "assistant", "image_url", image_url)
                    st.success("Imagem gerada!")
                    # Recarrega as mensagens para mostrar a nova imagem na tab de chat
                    messages_from_db = get_messages(st.session_state.current_conversation_id)
                    st.session_state.messages = [{"role": r, "type": t, "content": c} for r, t, c in messages_from_db]
                    st.rerun() # Força a atualização da UI para mostrar a mensagem na tab de chat
                except Exception as e:
                    st.error(f"Erro ao gerar imagem: {e}")

# --- TAB DE ANÁLISE DE ÁUDIO ---
with tab_audio:
    st.header("🎤 Análise de Áudio com Whisper e GPT-4o")
    uploaded_file = st.file_uploader("Carregue um ficheiro de áudio (MP3, WAV, M4A...)", type=["mp3", "wav", "m4a", "ogg"])
    if uploaded_file is not None:
        if st.session_state.current_conversation_id is None:
            new_id = create_conversation(f"Áudio: {uploaded_file.name}")
            st.session_state.current_conversation_id = new_id
            st.session_state.messages = []

        with st.spinner("A transcrever e analisar o áudio..."):
            try:
                # Transcrição com Whisper
                transcription = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=uploaded_file
                )
                transcribed_text = transcription.text
                add_message(st.session_state.current_conversation_id, "user", "text", f"(Áudio): {transcribed_text}")
                
                # Resposta do GPT-4o ao texto transcrito
                completion = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": transcribed_text}]
                )
                assistant_response = completion.choices[0].message.content
                add_message(st.session_state.current_conversation_id, "assistant", "text", assistant_response)

                st.success("Áudio processado!")
                # Recarrega as mensagens para mostrar o resultado na tab de chat
                messages_from_db = get_messages(st.session_state.current_conversation_id)
                st.session_state.messages = [{"role": r, "type": t, "content": c} for r, t, c in messages_from_db]
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar o áudio: {e}")