import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import logging

# Set up logging so we can see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MovieDatabaseCreator:
    def __init__(self):
        # Load our environment variables
        load_dotenv('config/.env')
        
        self.uri = os.getenv('NEO4J_URI')
        self.username = os.getenv('NEO4J_USERNAME') 
        self.password = os.getenv('NEO4J_PASSWORD')
        self.database = os.getenv('NEO4J_DATABASE')
        
        # Connect to Neo4j
        self.driver = GraphDatabase.driver(
            self.uri, 
            auth=(self.username, self.password)
        )
        logger.info("Connected to Neo4j!")
    
    def close(self):
        self.driver.close()
        logger.info("Connection closed!")
    
    def clear_database(self):
        """Clear everything in the database - fresh start!"""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared! Ready for fresh data.")
    
    def create_constraints_and_indexes(self):
        """Create constraints so we don't have duplicate data"""
        with self.driver.session(database=self.database) as session:
            # Make sure movie IDs are unique
            session.run("""
                CREATE CONSTRAINT movie_id_unique IF NOT EXISTS 
                FOR (m:Movie) REQUIRE m.movie_id IS UNIQUE
            """)
            
            # Make sure person IDs are unique  
            session.run("""
                CREATE CONSTRAINT person_id_unique IF NOT EXISTS 
                FOR (p:Person) REQUIRE p.person_id IS UNIQUE
            """)
            
            # Create indexes for faster searching
            session.run("""
                CREATE INDEX movie_title_index IF NOT EXISTS 
                FOR (m:Movie) ON (m.title)
            """)
            
            session.run("""
                CREATE INDEX person_name_index IF NOT EXISTS 
                FOR (p:Person) ON (p.name)
            """)
            
            logger.info("Created constraints and indexes!")
    
    def setup_database(self):
        """Run the full setup"""
        logger.info("Setting up movie database...")
        self.clear_database()
        self.create_constraints_and_indexes()
        logger.info("Database setup complete!")

if __name__ == "__main__":
    creator = MovieDatabaseCreator()
    creator.setup_database()
    creator.close()
    print("✅ Database is ready for data!")