from flask import Flask, request, jsonify
import openai
import os, re, time, gc, traceback
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- ✅ Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Helper: Split HTML into smaller logical chunks
def split_html_intelligently(html_content, max_chunk_size=1800):
    soup = BeautifulSoup(html_content, 'html.parser')
    head = soup.find('head')
    body = soup.find('body')

    head_content = str(head) if head else ""
    chunks, current_chunk = [], ""

    if body:
        for element in body.children:
            element_str = str(element)
            if len(element_str) > max_chunk_size:
                paragraphs = re.split(r'(</p>|</div>|</li>|</tr>)', element_str)
                for i in range(0, len(paragraphs), 2):
                    p = paragraphs[i] + (paragraphs[i + 1] if i + 1 < len(paragraphs) else '')
                    if len(current_chunk) + len(p) > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = p
                    else:
                        current_chunk += p
            else:
                if len(current_chunk) + len(element_str) > max_chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = element_str
                else:
                    current_chunk += element_str
        if current_chunk:
            chunks.append(current_chunk)

    return head_content, chunks


# --- Helper: Translate one HTML chunk
def translate_chunk_with_openai(html_chunk, model="gpt-4o-mini", target_lang="German"):
    print(f"🔄 Translating chunk ({len(html_chunk)} chars) → {target_lang} ...")
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"You are a professional HTML translator. Translate from English to {target_lang} while preserving ALL HTML tags, classes, and styles. Translate only visible text, never translate tags or CSS."
                },
                {"role": "user", "content": html_chunk}
            ],
            temperature=0.3,
            max_tokens=8000
        )
        translated_text = response.choices[0].message.content.strip()
        print(f"✅ Chunk translated ({len(translated_text)} chars)")
        return translated_text
    except Exception as e:
        print(f"❌ Error translating chunk: {e}")
        return html_chunk


# --- Endpoint: /translate-html
@app.route('/translate-html', methods=['POST'])
def translate_html():
    try:
        print("\n📥 New translation request received")
        data = request.get_json()
        if not data or 'html' not in data:
            return jsonify({'error': 'HTML content is required'}), 400

        html_content = data['html']
        target_lang = data.get('target_lang', 'German')
        model = data.get('model', 'gpt-4o-mini')

        print(f"📊 HTML size: {len(html_content)} chars, Target: {target_lang}")
        head_content, body_chunks = split_html_intelligently(html_content)
        print(f"✅ Split into {len(body_chunks)} chunks")

        translated_chunks = []
        for i, chunk in enumerate(body_chunks):
            print(f"📝 Processing chunk {i + 1}/{len(body_chunks)} ...")
            translated = translate_chunk_with_openai(chunk, model, target_lang)
            translated_chunks.append(translated)
            gc.collect()
            time.sleep(1)

        body_content = ''.join(translated_chunks)
        soup = BeautifulSoup(html_content, 'html.parser')
        body_tag = soup.find('body')
        body_attrs = ' '.join(
            [f'{k}="{v}"' if isinstance(v, str) else f'{k}="{" ".join(v)}"' for k, v in (body_tag.attrs.items() if body_tag else [])]
        )

        final_html = f"<html>{head_content}<body {body_attrs}>{body_content}</body></html>"
        print(f"✅ Translation complete, final size: {len(final_html)} chars")

        return jsonify({
            'success': True,
            'translated_html': final_html,
            'chunks_processed': len(body_chunks)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# --- Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'HTML Translator',
        'openai_configured': bool(openai.api_key)
    })


# --- Run server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting Flask server on port {port} ...")
    app.run(host="0.0.0.0", port=port)
