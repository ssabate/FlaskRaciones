from app import create_app, db
from app.models import Food
from sqlalchemy import func

def seed_db():
    app = create_app()
    with app.app_context():
        # Check if already seeded
        if db.session.scalar(db.select(Food.id).where(func.lower(Food.nombre) == "manzana").limit(1)):
            print("Database already seeded.")
            return

        base_foods = [
            Food(nombre="Manzana", hidratos_por_100g=14.0),
            Food(nombre="Plátano", hidratos_por_100g=23.0),
            Food(nombre="Pan Blanco", hidratos_por_100g=49.0),
            Food(nombre="Copos de Avena", hidratos_por_100g=60.0),
            Food(nombre="Arroz Blanco", hidratos_por_100g=28.0),
            Food(nombre="Pasta (Hervida)", hidratos_por_100g=30.0),
            Food(nombre="Leche Entera", hidratos_por_100g=4.7),
            Food(nombre="Galletas María", hidratos_por_100g=74.0),
        ]
        
        db.session.add_all(base_foods)
        db.session.commit()
        print(f"Added {len(base_foods)} base foods to the database.")

if __name__ == "__main__":
    seed_db()
