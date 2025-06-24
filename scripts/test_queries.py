import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

class MovieQueryTester:
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
    
    def close(self):
        self.driver.close()
    
    def test_basic_counts(self):
        """See how much data we have"""
        with self.driver.session(database=self.database) as session:
            # Count movies
            result = session.run("MATCH (m:Movie) RETURN count(m) as count")
            movie_count = result.single()['count']
            
            # Count people
            result = session.run("MATCH (p:Person) RETURN count(p) as count")
            people_count = result.single()['count']
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()['count']
            
            print(f"📊 Database Summary:")
            print(f"   Movies: {movie_count}")
            print(f"   People: {people_count}")
            print(f"   Relationships: {rel_count}")
    
    def test_sample_queries(self):
        """Try some fun queries"""
        with self.driver.session(database=self.database) as session:
            print(f"\n🎬 Sample Queries:")
            
            # Find highest rated movies
            print("\n🏆 Top 3 Highest Rated Movies:")
            result = session.run("""
                MATCH (m:Movie) 
                RETURN m.title, m.rating 
                ORDER BY m.rating DESC 
                LIMIT 3
            """)
            for record in result:
                print(f"   {record['m.title']}: ⭐ {record['m.rating']}")
            
            # Find Christopher Nolan movies
            print(f"\n🎥 Christopher Nolan Movies:")
            result = session.run("""
                MATCH (p:Person {name: 'Christopher Nolan'})-[:DIRECTED]->(m:Movie)
                RETURN m.title, m.year
                ORDER BY m.year
            """)
            for record in result:
                print(f"   {record['m.title']} ({record['m.year']})")
            
            # Find actors who worked in multiple movies
            print(f"\n👥 Actors in Multiple Movies:")
            result = session.run("""
                MATCH (p:Person)-[:ACTED_IN]->(m:Movie)
                WITH p, count(m) as movie_count
                WHERE movie_count > 1
                RETURN p.name, movie_count
                ORDER BY movie_count DESC
            """)
            for record in result:
                print(f"   {record['p.name']} ({record['movie_count']} movies)")

if __name__ == "__main__":
    tester = MovieQueryTester()
    tester.test_basic_counts()
    tester.test_sample_queries()
    tester.close()
    print("\n✅ All tests completed!")