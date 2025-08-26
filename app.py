from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
from db import students, books, librarians, API_KEYS

app = Flask(__name__)

def require_role(role="admin"):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            api_key = request.headers.get("X-API-KEY")
            if not api_key or api_key not in API_KEYS.values():
                return jsonify({"error": "Unauthorized - API Key required"}), 401

            # Admin-only routes
            if role == "admin" and api_key != API_KEYS["admin_key"]:
                return jsonify({"error": "Forbidden - Admin access only"}), 403

            # Staff or Admin routes
            if role == "staff" and api_key not in [API_KEYS["admin_key"], API_KEYS["staff_key"]]:
                return jsonify({"error": "Forbidden - Staff/Admin only"}), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator


#Student Entry
@app.post("/student_entry")
def student_entry():
    data = request.get_json()
    student_id = data["student_id"]

    if not student_id:
        return {"message": "student_id is required"}, 400
    
    if student_id not in students:
        return {"message": "Student not found"}, 404

    # Record entry time
    students[student_id]["in_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    students[student_id]["out_time"] = None  
    return {
        "student_id": student_id,
        "student_name": students[student_id]["student_name"],
        "in_time": students[student_id]["in_time"]
    }

#Student Exit
@app.put("/student_exit")
def student_exit():
    data = request.get_json()
    student_id = data.get("student_id")

    if not student_id:
        return {"message": "student_id is required"}, 400

    if student_id not in students:
        return {"message": "Student not found"}, 404

    # Check if student has entered
    if not students[student_id].get("in_time"):
        return {"message": "Student has not entered yet"}, 400

    # Record exit time
    students[student_id]["out_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "student_id": student_id,
        "out_time": students[student_id]["out_time"]
    }
# students who have entered and left
@app.route("/library_entries", methods=["GET"])
def view_library_entries():

    entered_students = {
        sid: {
            "student_name": info["student_name"],
            "in_time": info.get("in_time"),
            "out_time": info.get("out_time")
        }
        for sid, info in students.items() if info.get("in_time")
    }

    if not entered_students:
        return jsonify({"message": "No students have entered the library yet"}), 200

    return jsonify({"entered_students": entered_students}), 200

#  Borrowing book
@app.post("/borrow_book")
def borrow_book():
    data = request.get_json()
    student_id = data["student_id"]
    book_id = data["book_id"]
    librarian_id = data["librarian_id"]

    if student_id not in students:
        return {"message": "Student not found"}, 404
    if book_id not in books or books[book_id]["available"] == "No":
        return {"message": "Book not available"}, 400
    if librarian_id not in librarians:
        return {"message": "Librarian not found"}, 404

    date_of_issuing = datetime.now()
    date_of_returning = date_of_issuing + timedelta(days=7)

    record = {
        "book_id": book_id,
        "book_name": books[book_id]["book_name"],
        "issued_by": librarian_id,
        "date_of_issuing": date_of_issuing.strftime("%Y-%m-%d"),
        "date_of_returning": date_of_returning.strftime("%Y-%m-%d"),
        "fine": 0,
        "status": "Borrowed"
    }

    students[student_id]["borrowed_books"].append(record)
    books[book_id]["available"] = "No"

    return {
        "student_id": student_id,
        "student_name": students[student_id]["student_name"],
        "borrowed_books_count": len(students[student_id]["borrowed_books"]),
        "borrowed_book": record
    }

# Book Count 
@app.route("/count/<student_id>", methods=["GET"])
def get_book_count(student_id):
    if student_id not in students:
        return jsonify({"error": "Student ID not found"}), 404

    student = students[student_id]
    book_count = len(student["borrowed_books"])

    return jsonify({
        "student_id": student_id,
        "student_name": student["student_name"],
        "book_count": book_count,
        "borrowed_books": student["borrowed_books"]
    })

#  Returning  Book
@app.put("/return_book")
def return_book():
    data = request.get_json()
    student_id = data["student_id"]
    book_id = data["book_id"]

    if student_id not in students:
        return {"message": "Student not found"}, 404

    borrowed_books = students[student_id]["borrowed_books"]
    for book in borrowed_books:
        if book["book_id"] == book_id and book["status"] == "Borrowed":
            today = datetime.now()
            due_date = datetime.strptime(book["date_of_returning"], "%Y-%m-%d")
            actual_return_date = today.strftime("%Y-%m-%d")

            # Fine if late
            if today > due_date:
                delay = (today - due_date).days
                book["fine"] = delay * 2
            else:
                book["fine"] = 0

            book["status"] = "Returned"
            book["date_of_returning"] = actual_return_date
            books[book_id]["available"] = "Yes"

            return book

    return {"message": "Book not found in student's borrowed list"}, 404

#  Enquiry Books
@app.get("/book_enquiry/<book_id>")
def book_enquiry(book_id):
    if book_id not in books:
        return {"message": "Book not found"}, 404
    if books[book_id]["available"] == "Yes":
        return {"message": f"Book {book_id} - {books[book_id]['book_name']} is available"}
    else:
        return {"message": f"Book {book_id} - {books[book_id]['book_name']} is NOT available"}

# books and student details
@app.route("/students_books", methods=["GET"])
def students_books():
    all_students_books = {}
    for sid, info in students.items():
        all_students_books[sid] = {
            "student_name": info["student_name"],
            "borrowed_books": info.get("borrowed_books", [])
        }
    if not all_students_books:
        return jsonify({"message": "No students found"}), 200
    return jsonify({"students_books": all_students_books}), 200

#if book is missing
@app.put("/missing_book")
def missing_book():
    data = request.get_json()
    student_id = data["student_id"]
    book_id = data["book_id"]

    if student_id not in students:
        return {"message": "Student not found"}, 404

    borrowed_books = students[student_id]["borrowed_books"]
    for book in borrowed_books:
        if book["book_id"] == book_id and book["status"] == "Borrowed":
            book["fine"] = 500
            book["status"] = "Missing"
            books[book_id]["available"] = "No"
            return book

    return {"message": "Book not found in student's borrowed list"}, 404

#checking fines
@app.get("/fines/<student_id>")
def get_student_fines(student_id):
    # Check if student exists
    if student_id not in students:
        return {"error": "Student not found"}, 404

    student = students[student_id]
    fines_list = []

    # Check all borrowed books of that student
    for book in student["borrowed_books"]:
        if book["fine"] > 0 and book["status"] in ["Returned", "Missing"]:
            fines_list.append({
                "student_id": student_id,
                "student_name": student["student_name"],
                "book_id": book["book_id"],
                "book_name": book["book_name"],
                "status": book["status"],
                "fine": book["fine"]
            })

    # If no fines found
    if not fines_list:
        return {"message": f"No fines pending for student {student_id}"}, 200

    return {"fines": fines_list}, 200
# View all students with fines
@app.route("/students_fines", methods=["GET"])
def students_fines():
    students_with_fines = {}
    for sid, info in students.items():
        fines = []
        for book in info.get("borrowed_books", []):
            if book.get("fine", 0) > 0 and book.get("status") in ["Returned", "Missing"]:
                fines.append({
                    "book_id": book["book_id"],
                    "book_name": book["book_name"],
                    "fine": book["fine"],
                    "status": book["status"]
                })
        if fines:
            students_with_fines[sid] = {
                "student_name": info["student_name"],
                "fines": fines
            }
    if not students_with_fines:
        return jsonify({"message": "No fines pending"}), 200
    return jsonify({"students_with_fines": students_with_fines}), 200
#Student Management
#registering membership - admin only
@app.route("/register_student", methods=["POST"])
@require_role("admin")
def register_student():
    data = request.json
    student_id = data.get("student_id")
    student_name = data.get("student_name")

    if not student_id or not student_name:
        return jsonify({"error": "student_id and student_name required"}), 400

    if student_id in students:
        return jsonify({"error": "Student ID already exists"}), 400

    students[student_id] = {
        "student_name": student_name,
        "borrowed_books": [],
        "fine": 0
    }
    return jsonify({"message": f"Student {student_name} registered successfully", "student_id": student_id})

# Declining membership - admin only
@app.route("/remove_student/<student_id>", methods=["DELETE"])
@require_role("admin")
def remove_student(student_id):
    if student_id not in students:
        return jsonify({"error": "Student not found"}), 404

    student = students[student_id]

    if student.get("fine", 0) > 0:
        return jsonify({
            "error": f"Cannot remove student {student_id}. Pending fine: {student['fine']}"
        }), 400

    # Fine is zero, remove student
    students.pop(student_id)
    return jsonify({
        "message": f"Student {student_id} membership declined successfully (no pending fine)",
        "fine": 0
    })

#Book Management
# Adding book - admin only
@app.route("/add_book", methods=["POST"])
@require_role("admin")
def add_book_admin():
    data = request.json
    book_id = data.get("book_id")
    book_name = data.get("book_name")

    if book_id in books:
        return jsonify({"error": "Book ID already exists"}), 400

    books[book_id] = {"book_name": book_name, "available": "Yes"}
    return jsonify({"message": f"Book {book_name} added successfully"}), 201

# Removing book - admin only
@app.route("/delete_book/<book_id>", methods=["DELETE"])
@require_role("admin")
def delete_book_admin(book_id):
    if book_id not in books:
        return jsonify({"error": "Book not found"}), 404

    deleted = books.pop(book_id)
    return jsonify({"message": f"Book {book_id} deleted successfully", "deleted": deleted})

#librarian Management
#adding librarian
@app.route("/add_librarian", methods=["POST"])
@require_role("admin")
def add_librarian():
    data = request.json
    librarian_id = data.get("librarian_id")
    name = data.get("name")
    email = data.get("email")

    if librarian_id in librarians:
        return jsonify({"error": "Librarian ID already exists"}), 400

    librarians[librarian_id] = {"name": name, "email": email, "role": "staff"}
    return jsonify({"message": f"Librarian {name} added successfully"}), 201

#removing librarian
@app.route("/remove_librarian/<librarian_id>", methods=["DELETE"])
@require_role("admin")
def remove_librarian(librarian_id):
    if librarian_id not in librarians:
        return jsonify({"error": "Librarian not found"}), 404
    removed = librarians.pop(librarian_id)
    return jsonify({"message": f"Librarian {removed['name']} removed"})


if __name__ == "__main__":
    app.run(debug=True)

