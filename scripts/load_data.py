import os
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MovieDataLoader:
    def __init__(self):
        load_dotenv('config/.env')
        
        self.uri = os.getenv('NEO4J_URI')
        self.username = os.getenv('NEO4J_USERNAME')
        self.password = os.getenv('NEO4J_PASSWORD')
        self.database = os.getenv('NEO4J_DATABASE')
        
        self.driver = GraphDatabase.driver(
            self.uri, 
            auth=(self.username, self.password)
        )
        logger.info("Connected to Neo4j for data loading!")
    
    def close(self):
        self.driver.close()
    
    def load_movies(self):
        """Load all our movies into the graph"""
        movies_df = pd.read_csv('data/movies.csv')
        
        with self.driver.session(database=self.database) as session:
            for _, movie in movies_df.iterrows():
                query = """
                MERGE (m:Movie {movie_id: $movie_id})
                SET m.title = $title,
                    m.year = $year,
                    m.genre = $genre,
                    m.director = $director,
                    m.rating = $rating
                """
                session.run(query, 
                            movie_id=movie['movie_id'], 
                            title=movie['title'], 
                            year=movie['year'], 
                            genre=movie['genre'], 
                            director=movie['director'], 
                            rating=movie['rating'])
        logger.info(f"Loaded {len(movies_df)} movies!")

    def load_people(self):
        """Load all our people into the graph"""
        people_df = pd.read_csv('data/people.csv')
        
        with self.driver.session(database=self.database) as session:
            for _, person in people_df.iterrows():
                query = """
                MERGE (p:Person {
                    person_id: $person_id,
                    name: $name,
                    birth_year: $birth_year,
                    profession: $profession,
                    nationality: $nationality
                })
                """
                session.run(query, 
                            person_id=person['person_id'], 
                            name=person['name'], 
                            birth_year=person['birth_year'], 
                            profession=person['profession'], 
                            nationality=person['nationality'])
        logger.info(f"Loaded {len(people_df)} people!")

    def load_relationships(self):
        """Connect people to movies"""
        relationships_df = pd.read_csv('data/relationships.csv')
        
        with self.driver.session(database=self.database) as session:
            for _, rel in relationships_df.iterrows():
                # Dynamically build relationship type in query (Cypher does not allow parameter for rel type)
                rel_type = rel['relationship_type']
                query = f"""
                MATCH (p:Person {{name: $person_name}}), (m:Movie {{title: $movie_title}})
                CREATE (p)-[:{rel_type} {{character_name: $character_name}}]->(m)
                """
                session.run(query,
                            person_name=rel['person_name'],
                            movie_title=rel['movie_title'],
                            character_name=rel.get('character_name', None))
        logger.info(f"Loaded {len(relationships_df)} relationships!")
    
    def load_all_data(self):
        """Load everything in the right order"""
        logger.info("Starting data loading...")
        self.load_movies()
        self.load_people()
        self.load_relationships()
        logger.info("All data loaded successfully!")

if __name__ == "__main__":
    loader = MovieDataLoader()
    loader.load_all_data()
    loader.close()
    print("✅ All data loaded into Neo4j!")