
from app.models.entities import Article
from typing import Protocol

class ArticleClassifier(Protocol):
    async def classify(self, article: Article) -> str:
        ...

class ArcticleSummerizer(Protocol):
    async def summarize(self, article: Article) -> str:
        ...
    

class ArticleProcessor:
    def __init__(self, classifier: ArticleClassifier, summerizer: ArcticleSummerizer):
        self.classifier = classifier
        self.summerizer = summerizer

    async def process(self, article: Article) -> str:
        category = await self.classifier.classify(article)
        summary = await self.summerizer.summarize(article)
        return category, summary
    
class SimpleArticleClassifier(ArticleClassifier):
    async def classify(self, article: Article) -> str:
        # Simple classification logic based on title keywords
        if "news" in article.title.lower():
            return "News"
        elif "tutorial" in article.title.lower():
            return "Tutorial"
        else:
            return "General"

class SimpleArticleSummerizer(ArcticleSummerizer):
    async def summarize(self, article: Article) -> str:

        # Constraint checking of empty or null content
        if not article.content:
            return "No content available."
        # Simple summarization logic: return the first 100 characters of the content
        return article.content[:100] + "..." if len(article.content) > 100 else article.content
    