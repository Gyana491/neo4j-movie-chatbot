import os
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase
from google import genai
import logging

logger = logging.getLogger(__name__)

class GeminiMovieChatbot:
    def __init__(self):
        # Load environment variables
        load_dotenv('config/.env')
        # Neo4j setup
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_username = os.getenv('NEO4J_USERNAME')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.neo4j_database = os.getenv('NEO4J_DATABASE')
        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_username, self.neo4j_password)
        )
        # Configure Gemini API
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        # Common schema prompt
        self.schema = (
            "Given the Neo4j database schema with the following definitions:\n"
            "- Person nodes have properties: person_id (unique), name, birth_year, profession, nationality\n"
            "- Movie nodes have properties: movie_id (unique), title, year, genre, director, rating\n"
            "- Relationships: ACTED_IN has property character_name; DIRECTED has no extra properties\n"
            "Analyze the user question and extract 'intent' and 'entities'. Respond strictly with a JSON object containing 'intent' and 'entities'."
        )
        # Initialize history for context
        self.history = []

    def close(self):
        self.driver.close()

    # [Reuse data access methods from MovieChatbot]
    def generate_cypher(self, user_question):
        prompt = (
            "Given the Neo4j database schema with the following definitions:\n"
            "- Person(person_id, name, birth_year, profession, nationality)\n"
            "- Movie(movie_id, title, year, genre, director, rating)\n"
            "- Relationships: ACTED_IN(character_name), DIRECTED(no properties)\n"
            "Generate a Cypher query and JSON parameters to answer: '" + user_question + "'. Respond strictly with a JSON object containing 'query' and 'params'."
        )
        # Use generate_content to create JSON output
        resp = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = resp.text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].startswith("```"): lines = lines[:-1]
            raw = "\n".join(lines)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Gemini JSON parse error: %s", raw)
            return {}

    def search_movies_by_actor(self, actor_name):
        with self.driver.session(database=self.neo4j_database) as session:
            res = session.run(
                "MATCH (p:Person {name: $actor_name})-[:ACTED_IN]->(m:Movie) RETURN m.title AS title, m.year AS year, m.genre AS genre, m.rating AS rating ORDER BY m.year", actor_name=actor_name
            )
            return [r for r in res]
    def search_movies_by_director(self, director_name):
        with self.driver.session(database=self.neo4j_database) as session:
            res = session.run(
                "MATCH (p:Person {name: $director_name})-[:DIRECTED]->(m:Movie) RETURN m.title AS title, m.year AS year, m.genre AS genre, m.rating AS rating ORDER BY m.year", director_name=director_name
            )
            return [r for r in res]
    def search_movies_by_genre(self, genre):
        with self.driver.session(database=self.neo4j_database) as session:
            res = session.run(
                "MATCH (m:Movie {genre: $genre}) RETURN m.title AS title, m.year AS year, m.genre AS genre, m.rating AS rating ORDER BY m.rating DESC", genre=genre
            )
            return [r for r in res]
    def get_top_rated_movies(self, limit=5):
        with self.driver.session(database=self.neo4j_database) as session:
            res = session.run(
                "MATCH (m:Movie) RETURN m.title AS title, m.year AS year, m.genre AS genre, m.rating AS rating ORDER BY m.rating DESC LIMIT $limit", limit=limit
            )
            return [r for r in res]
    def get_movie_rating(self, title):
        with self.driver.session(database=self.neo4j_database) as session:
            rec = session.run("MATCH (m:Movie {title:$title}) RETURN m.rating AS rating", title=title).single()
            return rec
    def get_movie_details(self, title):
        with self.driver.session(database=self.neo4j_database) as session:
            rec = session.run(
                '''MATCH (m:Movie {title:$title}) OPTIONAL MATCH (a:Person)-[:ACTED_IN]->(m) OPTIONAL MATCH (d:Person)-[:DIRECTED]->(m) RETURN m.title AS title, m.year AS year, m.genre AS genre, m.rating AS rating, collect(DISTINCT a.name) AS actors, collect(DISTINCT d.name) AS directors''', title=title
            ).single()
            return rec

    def chat(self, user_question):
        # Record user question
        self.history.append({"role":"user","content": user_question})
        # Generate query & params
        info = self.generate_cypher(user_question)
        q = info.get('query')
        p = info.get('params', {})
        

        if not q:
            return "Sorry, couldn't generate query."
        # Run query
        with self.driver.session(database=self.neo4j_database) as session:
            records = [r for r in session.run(q, **p)]
        if not records:
            return "Sorry, I couldn't find anything."
        # Build raw results text
        raw_lines = [f"Results for '{user_question}':"]
        for rec in records:
            parts = []
            for k,v in rec.items():
                if hasattr(v,'items'):
                    for prop,val in v.items(): parts.append(f"{prop}: {val}")
                else: parts.append(f"{k}: {v}")
            raw_lines.append("- " + ", ".join(parts))
        raw_text = "\n".join(raw_lines)
        # Prepare system and user messages for final response
        system_msg = (
            "You are a friendly, human-like movie expert chatting with the user. "
            "Use the full conversation context to handle follow-up questions and references naturally. "
            "Respond in a warm, conversational tone as if talking in person, using Markdown when helpful. "
            "If the user asks for details or actors, query the database accordingly."
        )
        user_msg = (
            f"User question: {user_question}\n"
            "Database query results:\n"
            f"{raw_text}\n"
            "Please answer the question based on these results."
        )
        # Record user context
        self.history.append({"role": "user", "content": user_msg})
        # Combine system + history into prompt
        combined = system_msg + "\n" + "\n".join([f"{m['role']}: {m['content']}" for m in self.history])
        # Generate final answer with Gemini
        resp = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=combined
        )
        ans = resp.text.strip()
        # Record assistant response
        self.history.append({"role": "assistant", "content": ans})
        return ans
