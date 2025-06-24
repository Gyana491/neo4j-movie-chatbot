import os
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI
import logging
import re

# Set up logging so we can see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MovieChatbot:
    def __init__(self):
        # Load our settings
        load_dotenv('config/.env')
        
        # Neo4j connection
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_username = os.getenv('NEO4J_USERNAME')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.neo4j_database = os.getenv('NEO4J_DATABASE')
        
        self.driver = GraphDatabase.driver(
            self.neo4j_uri, 
            auth=(self.neo4j_username, self.neo4j_password)
        )
        
        # OpenRouter connection (using OpenAI SDK but pointing to OpenRouter)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv('OPENROUTER_API_KEY'),
        )
        
        print("🤖 Movie Chatbot is ready to help!")
        # Prompt template for intent extraction (with typo/casing correction instruction)
        self.schema = (
            "Given the Neo4j database schema with the following definitions:\n"
            "- Person nodes have properties: person_id (unique), name, birth_year, profession, nationality\n"
            "- Movie nodes have properties: movie_id (unique), title, year, genre, director, rating\n"
            "- Relationships: ACTED_IN has property character_name; DIRECTED has no extra properties\n"
            "If user entity names have typos or inconsistent casing, correct them to the nearest valid entries before extracting. "
            "Extract 'intent' and 'entities' from the user question and respond strictly with a JSON object containing 'intent' and 'entities'."
        )
        # Initialize chat history for session context
        self.history = []
    
    def close(self):
        self.driver.close()
    
    def search_movies_by_actor(self, actor_name):
        """Find movies where an actor appeared"""
        with self.driver.session(database=self.neo4j_database) as session:
            query = """
            MATCH (p:Person {name: $actor_name})-[:ACTED_IN]->(m:Movie)
            RETURN m.title, m.year, m.genre, m.rating
            ORDER BY m.year
            """
            result = session.run(query, actor_name=actor_name)
            return [record for record in result]

    def search_movies_by_director(self, director_name):
        """Find movies directed by someone"""
        with self.driver.session(database=self.neo4j_database) as session:
            query = """
            MATCH (p:Person {name: $director_name})-[:DIRECTED]->(m:Movie)
            RETURN m.title, m.year, m.genre, m.rating
            ORDER BY m.year
            """
            result = session.run(query, director_name=director_name)
            return [record for record in result]

    def search_movies_by_genre(self, genre):
        """Find movies by genre"""
        with self.driver.session(database=self.neo4j_database) as session:
            query = """
            MATCH (m:Movie {genre: $genre})
            RETURN m.title, m.year, m.director, m.rating
            ORDER BY m.rating DESC
            """
            result = session.run(query, genre=genre)
            return [record for record in result]

    def get_top_rated_movies(self, limit=5):
        """Get the highest rated movies"""
        with self.driver.session(database=self.neo4j_database) as session:
            query = """
            MATCH (m:Movie)
            RETURN m.title, m.year, m.genre, m.rating
            ORDER BY m.rating DESC
            LIMIT $limit
            """
            result = session.run(query, limit=limit)
            return [record for record in result]
    
    def get_movie_rating(self, title):
        """Get rating for a specific movie"""
        with self.driver.session(database=self.neo4j_database) as session:
            query = "MATCH (m:Movie {title: $title}) RETURN m.rating AS rating"
            record = session.run(query, title=title).single()
            return record

    def get_movie_details(self, title):
        """Get detailed info for a specific movie"""
        with self.driver.session(database=self.neo4j_database) as session:
            query = '''
            MATCH (m:Movie {title: $title})
            OPTIONAL MATCH (a:Person)-[:ACTED_IN]->(m)
            OPTIONAL MATCH (d:Person)-[:DIRECTED]->(m)
            RETURN m.title AS title, m.year AS year, m.genre AS genre, m.rating AS rating,
                   collect(DISTINCT a.name) AS actors, collect(DISTINCT d.name) AS directors
            '''
            record = session.run(query, title=title).single()
            return record

    def _friendly_rating_response(self, title):
        record = self.get_movie_rating(title)
        if not record or record.get('rating') is None:
            return f"Sorry, I couldn't find the rating for '{title}'."
        return f"The rating of '{title}' is {record['rating']}."

    def _friendly_details_response(self, title):
        record = self.get_movie_details(title)
        if not record or not record.get('title'):
            return f"Sorry, I couldn't find details for '{title}'."
        resp = [f"Here is information about '{title}':"]
        resp.append(f"- Year: {record['year']}")
        resp.append(f"- Genre: {record['genre']}")
        resp.append(f"- Rating: {record['rating']}")
        if record['actors']:
            resp.append(f"- Actors: {', '.join(record['actors'])}")
        if record['directors']:
            resp.append(f"- Directors: {', '.join(record['directors'])}")
        return "\n".join(resp)

    def understand_question(self, user_question):
        """Use AI to understand what the user wants"""
        # Use chat completion endpoint with messages
        response = self.client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[
                {"role": "system", "content": self.schema},
                {"role": "user", "content": f"Question: {user_question}"}
            ]
        )
        # Get the assistant's reply
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            # Remove leading fence
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # Remove trailing fence
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines)
        # Parse JSON output
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON: %s", raw)
            return {}

    def search_database(self, search_info):
        """Search the database based on extracted info"""
        intent = search_info.get('intent')
        entities = search_info.get('entities', {})

        if intent == 'search_movies_by_actor':
            return self.search_movies_by_actor(entities.get('actor_name'))
        elif intent == 'search_movies_by_director':
            return self.search_movies_by_director(entities.get('director_name'))
        elif intent == 'search_movies_by_genre':
            return self.search_movies_by_genre(entities.get('genre'))
        elif intent == 'get_top_rated_movies':
            return self.get_top_rated_movies(entities.get('limit', 5))
        else:
            return []

    def create_friendly_response(self, user_question, search_results, search_info):
        """Create a user-friendly response"""
        if not search_results:
            return "Sorry, I couldn't find anything for your question."

        response = f"Here are the results for your question: \"{user_question}\":\n"
        for result in search_results:
            response += f"- {result['m.title']} ({result['m.year']})\n"
        return response

    def generate_cypher(self, user_question):
        """Generate Cypher query and params from user question using AI"""
        prompt = (
            "Given the Neo4j database schema with the following definitions:\n"
            "- Person(person_id, name, birth_year, profession, nationality)\n"
            "- Movie(movie_id, title, year, genre, director, rating)\n"
            "- Relationships: ACTED_IN(character_name), DIRECTED(no properties)\n"
            "Generate a Cypher query and JSON parameters to answer: '" + user_question + "'. "
            "Respond strictly with a JSON object containing 'query' and 'params'."
        )
        response = self.client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[{"role": "system", "content": prompt}]
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            parts = raw.splitlines()
            if parts[0].startswith("```"): parts=parts[1:]
            if parts[-1].startswith("```"): parts=parts[:-1]
            raw = "\n".join(parts)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Failed to parse Cypher generation response: %s", raw)
            return {}

    def chat(self, user_question):
        """Main chat: generate Cypher via LLM and run it"""
        # Record user question in history
        self.history.append({"role": "user", "content": user_question})
         # Generate query & params via LLM
        info = self.generate_cypher(user_question)
        query = info.get('query')
        params = info.get('params', {})
         # Execute against Neo4j
        with self.driver.session(database=self.neo4j_database) as session:
            results = session.run(query, **params)
            records = [r for r in results]
        if not records:
            return "Sorry, I couldn't find anything for your question."
        # Prepare raw results lines
        raw_lines = [f"Results for '{user_question}':"]
        for record in records:
            parts = []
            for key, value in record.items():
                if hasattr(value, 'items'):
                    for prop, val in value.items():
                        parts.append(f"{prop}: {val}")
                else:
                    parts.append(f"{key}: {value}")
            raw_lines.append("- " + ", ".join(parts))
        raw_text = "\n".join(raw_lines)

        # Produce a ChatGPT-style answer using the raw results
        system_msg = (
            "You are ChatGPT, an AI assistant specialized in answering movie database queries. "
            "Use the provided query results to answer the user question concisely and clearly, in markdown format when appropriate."
        )
        user_msg = (
            f"User question: {user_question}\n"
            "Database query results:\n"
            f"{raw_text}\n"
            "Please answer the question based on these results."
        )
        # Append formatted user message for context
        self.history.append({"role": "user", "content": user_msg})
        chat_resp = self.client.chat.completions.create(
            model="deepseek/deepseek-chat-v3-0324:free",
            # Include session history for context
            messages=[{"role": "system", "content": system_msg}] + self.history
        )
        answer = chat_resp.choices[0].message.content.strip()
        # Record assistant response for context
        self.history.append({"role": "assistant", "content": answer})
        return answer

# Test our chatbot
if __name__ == "__main__":
    chatbot = MovieChatbot()
    
    # Test questions
    test_questions = [
        "What movies did Tom Hanks act in?",
        "Show me some action movies",
        "What are the best rated movies?",
        "Which movies did Christopher Nolan direct?",
        "Tell me about Inception",
        "What is the rating of The Matrix?"
    ]
    
    for question in test_questions:
        print(f"\n" + "="*50)
        answer = chatbot.chat(question)
        print(f"🤖 Chatbot: {answer}")
    
    chatbot.close()