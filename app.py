from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
from db import students, books, librarians, API_KEYS

app = Flask(__name__)

# Role-Based Access 
def require_role(role="admin"):             # Outer function, takes role argument (default = "admin")
    def decorator(f):                       # Actual decorator that wraps a route function
        @wraps(f)                           # Preserves original function name/docs
        def wrapper(*args, **kwargs):       # The new wrapped function
            api_key = request.headers.get("X-API-KEY")
            if not api_key or api_key not in API_KEYS.values():
                return jsonify({"error": "Unauthorized - API Key required"}), 401
            
            # Admin-only routes
            if role == "admin" and api_key != API_KEYS["admin_key"]:
                return jsonify({"error": "Forbidden - Admin access only"}), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator

# Student Entry
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

# Student Exit
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

# Students who have entered and left
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

# Borrowing book
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

# Book count each member has
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

# Returning Book
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

            # Remove returned book from student's borrowed list
            borrowed_books.remove(book)

            return {
                "message": "Book returned successfully",
                "book_id": book_id,
                "fine": book["fine"]
            }

    return {"message": "Book not found in student's borrowed list"}, 404

# Enquiry Books
@app.get("/book_enquiry/<book_id>")
def book_enquiry(book_id):
    if book_id not in books:
        return {"message": "Book not found"}, 404
    if books[book_id]["available"] == "Yes":
        return {"message": f"Book {book_id} - {books[book_id]['book_name']} is available"}
    else:
        return {"message": f"Book {book_id} - {books[book_id]['book_name']} is NOT available"}

# Books and Student Details
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

# Members and their IDs
@app.route("/members", methods=["GET"])
def get_members():
    members_list = [
        {"student_id": sid, "student_name": info["student_name"]}
        for sid, info in students.items()
    ]

    total_members = len(members_list)

    if not members_list:
        return jsonify({
            "total_members": 0,
            "message": "No members found"
        }), 200

    return jsonify({
        "total_members": total_members,
        "members": members_list
    }), 200


# Books currently issued (borrowed)
@app.route("/issued_books", methods=["GET"])
def get_issued_books():
    issued_books_list = []
    for sid, info in students.items():
        for book in info.get("borrowed_books", []):
            if book["status"] == "Borrowed":
                issued_books_list.append({
                    "book_id": book["book_id"],
                    "book_name": book["book_name"],
                    "borrowed_by_id": sid,
                    "borrowed_by_name": info["student_name"]
                })

    if not issued_books_list:
        return jsonify({"message": "No books are currently issued"}), 200

    return jsonify({"issued_books": issued_books_list}), 200

# Available Books
@app.route("/available_books", methods=["GET"])
def get_available_books():
    available_books_list = [
        {"book_id": bid, "book_name": info["book_name"]}
        for bid, info in books.items() if info["available"] == "Yes"
    ]

    if not available_books_list:
        return jsonify({"message": "No books are currently available"}), 200

    return jsonify({"available_books": available_books_list}), 200

# If Book is Missing
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

 # Checking Fines
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

# Student Management
# Registering membership - admin only
@app.route("/register_student", methods=["POST"])
@require_role("admin")
def register_student():
    data = request.json
    student_id = data.get("student_id")
    student_name = data.get("student_name")
    password = data.get("password")  # get password from request

    if not student_id or not student_name or not password:
        return jsonify({"error": "student_id, student_name, and password are required"}), 400

    if student_id in students:
        return jsonify({"error": "Student ID already exists"}), 400

    students[student_id] = {
        "student_name": student_name,
        "borrowed_books": [],
        "fine": 0,
        "password": password  # store password
    }

    # Mask password in response
    response_student = students[student_id].copy()
    response_student["password"] = "#"

    return jsonify({"message": f"Student {student_name} registered successfully",
                    "student": response_student})

# Declining membership - admin only or student self-request
@app.route("/remove_student/<student_id>", methods=["DELETE"])
@app.route("/decline/<student_id>", methods=["DELETE"])  
def remove_student(student_id):
    data = request.json
    password = data.get("password")  # password provided by student
    is_admin = request.headers.get("X-API-KEY") == API_KEYS.get("admin_key")  # check admin

    if student_id not in students:
        return jsonify({"error": "Student not found"}), 404

    student = students[student_id]

    # Calculate total fines from all borrowed books
    total_fine = sum(book.get("fine", 0) for book in student["borrowed_books"])

    # Admin override → can remove regardless of fine or password
    if is_admin:
        students.pop(student_id)
        return jsonify({
            "message": f"Student {student_id} membership declined by admin",
            "fine": total_fine
        })

    # Student self-request → check password
    if not password or password != student.get("password"):
        return jsonify({"error": "Password incorrect"}), 403

    # Check fine
    if total_fine == 0:
        # Fine is zero → remove automatically
        students.pop(student_id)
        return jsonify({
            "message": f"Student {student_id} membership declined successfully (no pending fine)",
            "fine": 0
        })
    else:
        # Fine > 0 → cannot remove automatically, must contact admin
        return jsonify({
            "message": f"Cannot remove student {student_id}. Pending fine: {total_fine}. Please contact admin.",
            "fine": total_fine
        }), 400

# Paying Fine
@app.put("/pay_fine/<student_id>")
def pay_fine(student_id):
    if student_id not in students:
        return jsonify({"error": "Student not found"}), 404

    student = students[student_id]

    # Calculate total fine
    total_fine = sum(book.get("fine", 0) for book in student["borrowed_books"])

    if total_fine == 0:
        return jsonify({"message": "No fine pending"}), 200

    # Get payment amount from request body
    data = request.json
    amount = data.get("amount")

    if not amount or amount <= 0:
        return jsonify({"error": "Please provide a valid payment amount"}), 400

    if amount > total_fine:
        return jsonify({"error": f"Payment exceeds pending fine. Pending fine is {total_fine}"}), 400

    # Deduct amount from fines (distribute across borrowed books)
    remaining = amount
    for book in student["borrowed_books"]:
        if book["fine"] > 0 and remaining > 0:
            if remaining >= book["fine"]:
                remaining -= book["fine"]
                book["fine"] = 0
            else:
                book["fine"] -= remaining
                remaining = 0

    # Recalculate total fine after payment
    new_total_fine = sum(book.get("fine", 0) for book in student["borrowed_books"])

    return jsonify({
        "message": f"Payment successful. Paid {amount}.",
        "student_id": student_id,
        "student_name": student["student_name"],
        "paid_amount": amount,
        "remaining_fine": new_total_fine
    }), 200
    
# Book Management
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


# Librarian Management
# Add librarian - admin only
@app.route("/add_librarian", methods=["POST"])
@require_role("admin")
def add_librarian():
    data = request.json
    librarian_id = data.get("librarian_id")
    librarian_name = data.get("librarian_name")

    if not librarian_id or not librarian_name:
        return jsonify({"error": "librarian_id and librarian_name are required"}), 400

    if librarian_id in librarians:
        return jsonify({"error": "Librarian ID already exists"}), 400

    librarians[librarian_id] = {"librarian_name": librarian_name}
    return jsonify({"message": f"Librarian {librarian_name} added successfully"}), 201

# Remove librarian - admin only
@app.route("/remove_librarian/<librarian_id>", methods=["DELETE"])
@require_role("admin")
def remove_librarian(librarian_id):
    if librarian_id not in librarians:
        return jsonify({"error": "Librarian not found"}), 404
    
    removed = librarians.pop(librarian_id)
    return jsonify({"message": f"Librarian {removed['librarian_name']} removed"})


# List all librarians 
@app.route("/list_librarians", methods=["GET"])
def list_librarians():
    result = [{"librarian_id": lid, "librarian_name": info["librarian_name"]} 
              for lid, info in librarians.items()]
    return jsonify({"librarians": result})

# Main function
if __name__ == "__main__":
    app.run(debug=True)