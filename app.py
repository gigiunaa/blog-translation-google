from flask import Flask, request, jsonify
from openai import OpenAI
from bs4 import BeautifulSoup
import os
import traceback
import time

app = Flask(__name__)

# =========================
# CONFIG
# =========================
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

# =========================
# CORE TRANSLATION FUNCTION
# =========================
def translate_visible_texts(html_content, target_lang="German", model="gpt-4o-mini"):
    soup = BeautifulSoup(html_content, "html.parser")
    tags_to_translate = soup.find_all(["h1", "h2", "h3", "h4", "p", "span", "a", "li", "strong", "em"])

    print(f"🧩 Found {len(tags_to_translate)} translatable elements")

    for i, tag in enumerate(tags_to_translate, start=1):
        text = tag.get_text(strip=True)
        if not text:
            continue

        print(f"🌐 Translating [{i}/{len(tags_to_translate)}]: {text[:60]}...")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Translate the following text from English to {target_lang}. "
                                   f"Return only translated text. Do not translate HTML tags, class, style, or IDs."
                    },
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=500
            )

            translated_text = response.choices[0].message.content.strip()
            tag.string = translated_text
            time.sleep(0.5)  # Slight delay to avoid rate limits
        except Exception as e:
            print(f"⚠️ Translation failed for '{text[:40]}': {e}")
            continue

    return str(soup)

# =========================
# ROUTES
# =========================
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "HTML Translator",
        "status": "running",
        "usage": "POST /translate-html with { html, target_lang }"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "openai_key_set": bool(OPENAI_KEY)
    })


@app.route("/translate-html", methods=["POST"])
def translate_html():
    try:
        data = request.get_json()
        if not data or "html" not in data:
            return jsonify({"success": False, "error": "Missing 'html' field"}), 400

        html_content = data["html"]
        target_lang = data.get("target_lang", "German")
        model = data.get("model", "gpt-4o-mini")

        print(f"\n📥 New translation request")
        print(f"🌍 Target: {target_lang}")
        print(f"📊 HTML size: {len(html_content)} chars")

        translated_html = translate_visible_texts(html_content, target_lang, model)

        print(f"✅ Translation complete! Final length: {len(translated_html)} chars\n")

        return jsonify({
            "success": True,
            "target_language": target_lang,
            "translated_html": translated_html
        })

    except Exception as e:
        print(f"❌ ERROR: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)
