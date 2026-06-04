# Entrypoint: create Flask app and render the read-only article view at /.

from flask import Flask, render_template_string

from news_agent.db import get_latest_run, get_processed_articles, init_db

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Biotech News Monitor</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
      margin: 0;
      background: #f6f8fb;
      color: #1f2933;
    }
    main {
      max-width: 860px;
      margin: 0 auto;
      padding: 2rem 1.25rem 3rem;
    }
    header {
      background: #ffffff;
      border: 1px solid #dbe2ea;
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
    }
    h1 {
      margin: 0 0 0.5rem;
      font-size: 1.75rem;
    }
    .meta {
      color: #52606d;
      font-size: 0.95rem;
    }
    .empty {
      background: #ffffff;
      border: 1px dashed #cbd2d9;
      border-radius: 10px;
      padding: 2rem;
      text-align: center;
      color: #52606d;
    }
    .article {
      background: #ffffff;
      border: 1px solid #dbe2ea;
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1rem;
    }
    .article h2 {
      margin: 0 0 0.5rem;
      font-size: 1.2rem;
    }
    .article h2 a {
      color: #155eef;
      text-decoration: none;
    }
    .article h2 a:hover {
      text-decoration: underline;
    }
    .article-meta {
      color: #52606d;
      font-size: 0.9rem;
      margin-bottom: 0.75rem;
    }
    .score {
      display: inline-block;
      background: #e3f5ff;
      color: #0b69a3;
      border-radius: 999px;
      padding: 0.1rem 0.55rem;
      font-weight: 600;
      margin-right: 0.5rem;
    }
    .summary {
      margin: 0;
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Biotech News Monitor</h1>
      {% if latest_run %}
      <p class="meta">
        Latest run:
        {{ latest_run.finished_at or latest_run.started_at or "unknown time" }}
        · status {{ latest_run.status }}
      </p>
      {% else %}
      <p class="meta">No monitoring runs yet.</p>
      {% endif %}
    </header>

    {% if articles %}
      {% for article in articles %}
      <article class="article">
        <h2>
          {% if article.url %}
          <a href="{{ article.url }}" target="_blank" rel="noopener noreferrer">{{ article.title }}</a>
          {% else %}
          {{ article.title }}
          {% endif %}
        </h2>
        <p class="article-meta">
          <span class="score">Score {{ article.relevance_score }}</span>
          {{ article.source }}
          {% if article.published_at %}
          · {{ article.published_at }}
          {% endif %}
        </p>
        <p class="summary">{{ article.summary }}</p>
      </article>
      {% endfor %}
    {% else %}
      <div class="empty">
        <p>No relevant processed articles yet.</p>
      </div>
    {% endif %}
  </main>
</body>
</html>
"""


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        init_db()
        return render_template_string(
            PAGE_TEMPLATE,
            latest_run=get_latest_run(),
            articles=get_processed_articles(),
        )

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
