from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from db import students, books, librarians

app = Flask(__name__)

# 1. Student entry
@app.post("/student_entry")
def student_entry():
    data = request.get_json()
    student_id = data["student_id"]

    if student_id not in students:
        return {"message": "Student not found"}, 404

    students[student_id]["in_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    students[student_id]["out_time"] = None
    return {
        "student_id": student_id,
        "student_name": students[student_id]["student_name"],
        "in_time": students[student_id]["in_time"]
    }

# 2. Student exit
@app.put("/student_exit/<student_id>")
def student_exit(student_id):
    if student_id not in students:
        return {"message": "Student not found"}, 404

    students[student_id]["out_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "student_id": student_id,
        "out_time": students[student_id]["out_time"]
    }

# 3. Borrow book
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

# 4. Book enquiry
@app.get("/book_enquiry/<book_id>")
def book_enquiry(book_id):
    if book_id not in books:
        return {"message": "Book not found"}, 404
    if books[book_id]["available"] == "Yes":
        return {"message": f"✅ Book {book_id} - {books[book_id]['book_name']} is available"}
    else:
        return {"message": f"❌ Book {book_id} - {books[book_id]['book_name']} is NOT available"}

# 5. Return book
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

# 6. Mark book as missing
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
            books[book_id]["available"] = "No"  # Book lost permanently
            return book

    return {"message": "Book not found in student's borrowed list"}, 404

# 7. Show all students with pending fines
@app.get("/fines")
def get_fines():
    fines_list = []
    for student_id, student in students.items():
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

    if not fines_list:
        return {"message": "No fines pending"}, 200

    return {"fines": fines_list}

# 8. Register New Student
@app.route('/register_student', methods=['POST'])
def register_student():
    data = request.json
    student_id = data.get("student_id")
    student_name = data.get("student_name")

    if not student_id or not student_name:
        return jsonify({"error": "student_id and student_name are required"}), 400

    if student_id in students:
        return jsonify({"error": "Student ID already exists"}), 400

    students[student_id] = {
        "student_name": student_name,
        "in_time": None,
        "out_time": None,
        "borrowed_books": []
    }

    return jsonify({"message": f"Student {student_name} registered successfully", "student_id": student_id})

# 9. Remove Student (Decline Membership)
@app.route('/remove_student/<student_id>', methods=['DELETE'])
def remove_student(student_id):
    if student_id not in students:
        return jsonify({"error": "Student not found"}), 404

    student = students[student_id]
    total_fine = sum(book.get("fine", 0) for book in student["borrowed_books"])

    # Remove student from db
    removed_student = students.pop(student_id)

    return jsonify({
        "message": f"Student {removed_student['student_name']} removed successfully",
        "total_fine": total_fine
    })
#10.book count
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
#11.deleting_ book
@app.route("/delete_book/<book_id>", methods=["DELETE"])
def delete_book(book_id):
    if book_id not in books:
        return jsonify({"error": "Book not found"}), 404

    # Before deleting, check if the book is borrowed by any student
    for student_id, student in students.items():
        for book in student["borrowed_books"]:
            if book["book_id"] == book_id and book["status"] == "Borrowed":
                return jsonify({
                    "error": "Book cannot be deleted because it is currently borrowed",
                    "student_id": student_id,
                    "student_name": student["student_name"]
                }), 400

    # If not borrowed, delete book from DB
    deleted_book = books.pop(book_id)
    return jsonify({
        "message": f"Book {book_id} deleted successfully",
        "deleted_book": deleted_book
    })
from flask import Flask, jsonify, request
from db import books, students, librarians

app = Flask(__name__)

# ------------------- ADD BOOK -------------------
@app.route("/add_book", methods=["POST"])
def add_book():
    data = request.get_json()
    book_id = data.get("book_id")
    book_name = data.get("book_name")

    if not book_id or not book_name:
        return jsonify({"error": "book_id and book_name are required"}), 400

    if book_id in books:
        return jsonify({"error": "Book ID already exists"}), 400

    books[book_id] = {"book_name": book_name, "available": "Yes"}
    return jsonify({"message": f"Book {book_name} added successfully", "book": books[book_id]}), 201


# ------------------- ADD LIBRARIAN -------------------
@app.route("/add_librarian", methods=["POST"])
def add_librarian():
    data = request.get_json()
    librarian_id = data.get("librarian_id")
    name = data.get("name")
    email = data.get("email")

    if not librarian_id or not name or not email:
        return jsonify({"error": "librarian_id, name, and email are required"}), 400

    if librarian_id in librarians:
        return jsonify({"error": "Librarian ID already exists"}), 400

    librarians[librarian_id] = {"name": name, "email": email}
    return jsonify({"message": f"Librarian {name} added successfully", "librarian": librarians[librarian_id]}), 201


# ------------------- REMOVE LIBRARIAN -------------------
@app.route("/remove_librarian/<librarian_id>", methods=["DELETE"])
def remove_librarian(librarian_id):
    if librarian_id not in librarians:
        return jsonify({"error": "Librarian not found"}), 404

    removed_librarian = librarians.pop(librarian_id)
    return jsonify({"message": f"Librarian {removed_librarian['name']} removed successfully",
                    "removed_librarian": removed_librarian}), 200


if __name__ == "__main__":
    app.run(debug=True)
