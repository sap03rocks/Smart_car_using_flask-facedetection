from app import app, db, User,Admin,Intruder # Replace with actual filename (without .py extension)

def delete_all_intruders():
    with app.app_context():
        db.session.query(User).delete()
        db.session.query(Intruder).delete()
        db.session.query(Admin).delete()
        db.session.commit()
        print("All intruder records have been deleted.")

if __name__ == "__main__":
    delete_all_intruders()
