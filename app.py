from flask import Flask, request, jsonify
from openai import OpenAI
import os, re, time, gc, traceback
from bs4 import BeautifulSoup

app = Flask(__name__)

# === Initialize OpenAI client ===
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    print("⚠️ Missing OPENAI_API_KEY environment variable!")
client = OpenAI(api_key=OPENAI_KEY)

# === Split HTML into chunks ===
def split_html_intelligently(html_content, max_chunk_size=1800):
    """Split HTML into manageable chunks without breaking tags."""
    soup = BeautifulSoup(html_content, "html.parser")
    head = soup.find("head")
    body = soup.find("body")

    head_content = str(head) if head else ""
    chunks, current_chunk = [], ""

    if not body:
        return head_content, [html_content]

    for element in body.children:
        element_str = str(element)
        if not element_str.strip():
            continue
        if len(element_str) > max_chunk_size:
            paragraphs = re.split(r"(</p>|</div>|</li>|</tr>)", element_str)
            for i in range(0, len(paragraphs), 2):
                p = paragraphs[i] + (paragraphs[i + 1] if i + 1 < len(paragraphs) else "")
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


# === Translate one chunk ===
def translate_chunk_with_openai(html_chunk, model="gpt-4o-mini", target_lang="German"):
    print(f"🔄 Translating chunk ({len(html_chunk)} chars) → {target_lang} ...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional HTML translator.
Translate from English to {target_lang} while preserving ALL HTML tags, classes, and inline styles.

RULES:
1. Translate ONLY visible text.
2. NEVER translate HTML tags, attributes, or CSS.
3. Preserve the exact HTML structure.
4. Return ONLY the translated HTML (no explanations)."""
                },
                {"role": "user", "content": html_chunk},
            ],
            temperature=0.3,
            max_tokens=8000,
        )
        text = response.choices[0].message.content.strip()
        print(f"✅ Chunk translated ({len(text)} chars)")
        return text
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        return html_chunk  # fallback


# === /translate-html endpoint ===
@app.route("/translate-html", methods=["POST"])
def translate_html():
    try:
        print("\n📥 New translation request received")
        data = request.get_json(force=True, silent=True)
        if not data or "html" not in data:
            return jsonify({"error": "Missing 'html' field in request"}), 400

        html_content = data["html"]
        target_lang = data.get("target_lang", "German")
        model = data.get("model", "gpt-4o-mini")

        print(f"📊 HTML size: {len(html_content)} chars | Target: {target_lang}")
        head_content, body_chunks = split_html_intelligently(html_content)
        print(f"✂️ Split into {len(body_chunks)} chunks")

        translated_chunks = []
        for i, chunk in enumerate(body_chunks):
            print(f"📝 Processing chunk {i+1}/{len(body_chunks)} ...")
            translated_chunks.append(
                translate_chunk_with_openai(chunk, model, target_lang)
            )
            gc.collect()
            time.sleep(1)

        body_content = "".join(translated_chunks)
        soup = BeautifulSoup(html_content, "html.parser")
        body_tag = soup.find("body")
        body_attrs = ""
        if body_tag:
            attrs = body_tag.attrs
            body_attrs = " ".join(
                [f'{k}="{v}"' if isinstance(v, str) else f'{k}="{" ".join(v)}"' for k, v in attrs.items()]
            )

        final_html = f"<html>{head_content}<body {body_attrs}>{body_content}</body></html>"
        print(f"✅ Translation completed, final size: {len(final_html)} chars")

        return jsonify({
            "success": True,
            "translated_html": final_html,
            "chunks_processed": len(body_chunks)
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# === /health endpoint ===
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "HTML Translator",
        "openai_configured": bool(OPENAI_KEY)
    })


# === Run app ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting Flask server on port {port} ...")
    app.run(host="0.0.0.0", port=port)
