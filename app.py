# app.py
import streamlit as st
from openai import OpenAI
import tempfile
import warnings
import os

warnings.filterwarnings("ignore")

st.set_page_config(page_title="The Shakespeare Bot: Ask William Anything!", page_icon="🎭", layout="wide")

# Sidebar / API key
with st.sidebar:
    st.image('images/logo1.png')
    st.image('images/logo0.png')
    api_key = st.text_input("Enter your OpenAI API token:", type="password")
    if api_key and api_key.startswith("sk-") and len(api_key) > 40:
        st.success("API key looks good!", icon="👉")
    elif api_key:
        st.warning("Invalid API key format.", icon="⚠️")
    else:
        st.info("Enter your API key to begin.", icon="ℹ️")
    st.markdown("---")
    options = st.radio("Dashboard", ["Home", "About Me", "Ask William"])

SYSTEM_PROMPT = """
You are William Shakespeare, the exceptionally brilliant and literary genius of the English drama.
Answer questions about your plays, sonnets, and characters using wit, sharp humour, confidence,
and deep literary insight. Focus strictly on Shakespearean literature.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []

def safe_get_assistant_text(response):
    """
    Attempt a few ways to extract text from a chat completion response object.
    Works across slightly different return shapes.
    """
    try:
        # preferred: object attribute
        return response.choices[0].message.content
    except Exception:
        try:
            # fallback: mapping-like
            return response.choices[0].message["content"]
        except Exception:
            try:
                return response.choices[0]["message"]["content"]
            except Exception:
                # last resort: string representation
                return str(response)

def safe_get_transcription_text(transcription):
    try:
        return getattr(transcription, "text", None) or transcription.get("text")  # handles attr or dict
    except Exception:
        return None

def safe_get_audio_bytes(audio_response):
    """
    audio_response may be a streaming / file-like object or wrapper.
    Attempt common access patterns.
    """
    try:
        if hasattr(audio_response, "read"):
            return audio_response.read()
        if hasattr(audio_response, "content"):
            return audio_response.content
        if isinstance(audio_response, (bytes, bytearray)):
            return bytes(audio_response)
        # if it's a dict-like with 'data' or 'audio' keys
        if isinstance(audio_response, dict):
            for k in ("audio", "data", "content"):
                if k in audio_response:
                    return audio_response[k]
    except Exception:
        pass
    return None

# --- Pages ---
if options == "Home":
    st.title("The Shakespeare Bot")
    st.markdown("<p style='color:red; font-weight:bold;'>Enter your API token to use the bot.</p>", unsafe_allow_html=True)
    st.write("Ask William Shakespeare anything about his plays and sonnets using text or voice.")

elif options == "About Me":
    st.title("About William Shakespeare")
    st.write("William Shakespeare (1564–1616) — playwright, poet, and actor. Ask about plays, sonnets, themes and characters.")

elif options == "Ask William":
    st.title("Ask William Shakespeare!")
    st.write("You can type a question or upload a voice recording (wav/mp3/m4a).")
    
    # Text input
    user_question = st.text_input("Type your question:", key="text_question")

    # Voice input (file uploader)
    st.markdown("**Or upload a voice question**")
    voice_file = st.file_uploader("Upload audio (wav, mp3, m4a)", type=["wav", "mp3", "m4a"], key="voice_uploader")

    voice_style = st.selectbox(
    "Choose Shakespeare's Voice Style:",
    [
        "Dramatic Stage Voice",
        "Warm, Noble Bard",
        "Aged Shakespeare",
        "Playful Jester",
        "Royal Court Voice",
        "Whispered Bard"
    ]
)
    if st.session_state.messages:
        st.markdown("### Conversation")
        for msg in st.session_state.messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "user":
                st.markdown(f"**You:** {content}")
            elif role == "assistant":
                st.markdown(f"**William Shakespeare:** {content}")

    col1, col2 = st.columns([1, 1])
    submit = col1.button("Submit")
    clear = col2.button("Clear Conversation")

    if clear:
        st.session_state.messages = []
        st.experimental_rerun()

    if submit:
        if not api_key or not api_key.startswith("sk-"):
            st.warning("Enter a valid OpenAI API key in the sidebar.")
        else:
            client = OpenAI(api_key=api_key)

            # ensure system prompt present
            if not any(m["role"] == "system" for m in st.session_state.messages):
                st.session_state.messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

            # determine final question: prefer uploaded voice if present, else typed text
            final_question = (user_question or "").strip()

            if voice_file is not None:
                # save temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(voice_file.name)[1]) as tmp:
                    tmp.write(voice_file.read())
                    tmp_path = tmp.name

                st.info("Transcribing audio…")
                try:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=open(tmp_path, "rb")
                    )
                    trans_text = safe_get_transcription_text(transcription)
                    if trans_text:
                        final_question = trans_text
                        st.markdown(f"**Transcribed:** {final_question}")
                    else:
                        st.warning("Could not extract transcription text; using typed input if available.")
                except Exception as e:
                    st.error(f"Transcription failed: {e}")
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            if not final_question:
                st.warning("Provide a typed question or upload a voice file.")
                st.stop()

            # append user message to conversation
            st.session_state.messages.append({"role": "user", "content": final_question})

            # call chat completion
            try:
                with st.spinner("The Bard is composing his reply..."):
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=st.session_state.messages,
                        temperature=0.7,
                        max_tokens=800
                    )

                assistant_reply = safe_get_assistant_text(response)
                # append assistant reply
                st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

                st.success("Here’s what The Bard says:")
                st.write(assistant_reply)                
                # --- Text-to-speech (TTS) ---
                voice_map = {"Dramatic Stage Voice": "alloy",
                                "Warm, Noble Bard": "verse",
                                "Aged Shakespeare": "sage",
                                "Playful Jester": "spark",
                                "Royal Court Voice": "duet",
                                "Whispered Bard": "whisper"
                            },
                chosen_voice = voice_map[voice_style]

                try:
                    with st.spinner("Generating spoken reply..."):
                        audio_response = client.audio.speech.create(
                            model="gpt-4o-mini-tts",
                            voice=chosen_voice,
                            input=assistant_reply
                        )
                audio_bytes = safe_get_audio_bytes(audio_response)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3")
                    else:
                        st.warning("Audio generation returned no bytes; reply shown as text only.")
                except Exception as e:
                    st.warning(f"TTS generation failed: {e}")

            except Exception as e:
                st.error(f"OpenAI request failed: {e}")

st.markdown("---")
st.caption("Shakespeare Bot — voice and text. Keep questions focused on Shakespeare's works.")
