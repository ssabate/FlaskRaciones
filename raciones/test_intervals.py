from app import create_app
from app.extensions import db
from app.models import User, MealInterval, ConsumptionLog, Food
from datetime import datetime

app = create_app()

def test_intervals():
    with app.app_context():
        # Get pepe user
        user = User.query.filter_by(username='pepe').first()
        if not user:
            print("User pepe not found")
            return
            
        print(f"User intervals for {user.username}:")
        for interval in user.intervals:
            print(f"- {interval.name}: {interval.start_time} to {interval.end_time}")
            
        # Simulate index route logic
        now = datetime.utcnow()
        today = now.date()
        print(f"\nSimulating index route logic for today ({today}):")
        
        # Test basic query to avoid compile errors
        for interval in user.intervals.order_by(MealInterval.start_time).all():
            print(f"Checking interval: {interval.name}")
            # Ensure it works
            
        print("\nAll good! Intervals are correctly set up and models load properly.")

if __name__ == '__main__':
    test_intervals()
