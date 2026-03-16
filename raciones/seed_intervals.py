from app import create_app
from app.extensions import db
from app.models import User, MealInterval
from datetime import time

app = create_app()

def seed_default_intervals():
    with app.app_context():
        users = User.query.all()
        added = 0
        for user in users:
            # Check if user already has intervals
            if user.intervals.count() == 0:
                print(f"Adding default intervals for user {user.username}")
                intervals = [
                    MealInterval(user_id=user.id, name='Desayuno', start_time=time(6, 0), end_time=time(11, 59), target_hc=None),
                    MealInterval(user_id=user.id, name='Almuerzo', start_time=time(12, 0), end_time=time(16, 59), target_hc=None),
                    MealInterval(user_id=user.id, name='Cena', start_time=time(19, 0), end_time=time(5, 59), target_hc=None)
                ]
                db.session.add_all(intervals)
                added += 1
        
        if added > 0:
            db.session.commit()
            print(f"Added default intervals for {added} users.")
        else:
            print("No users needed default intervals.")

if __name__ == '__main__':
    seed_default_intervals()
