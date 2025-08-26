from flask import Flask, request
from db import students, books
from datetime import datetime, timedelta

app = Flask(__name__)

# 1. Student entry
@app.post("/student_entry")
def student_entry():
    data = request.get_json()
    student_id = data["student_id"]

    students[student_id] = {
        "student_name": data["student_name"],
        "librarian_id": data["librarian_id"],
        "in_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "out_time": None,
        "borrowed_books": []
    }
    return students[student_id]


# 1. Student exit
@app.put("/student_exit/<student_id>")
def student_exit(student_id):
    if student_id not in students:
        return {"message": "Student not found"}, 404
    students[student_id]["out_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return students[student_id]


# 2. Borrow book
@app.post("/borrow_book")
def borrow_book():
    data = request.get_json()
    student_id = data["student_id"]
    book_id = data["book_id"]

    if student_id not in students:
        return {"message": "Student not found"}, 404
    if book_id not in books or books[book_id]["available"] == "No":
        return {"message": "Book not available"}, 400

    date_of_issuing = datetime.now()
    date_of_returning = date_of_issuing + timedelta(days=7)

    record = {
        "book_id": book_id,
        "book_name": books[book_id]["name"],
        "issued_by": data["librarian_id"],
        "date_of_issuing": date_of_issuing.strftime("%Y-%m-%d"),
        "date_of_returning": date_of_returning.strftime("%Y-%m-%d"),
        "fine": 0,
        "status": "Borrowed"
    }

    students[student_id]["borrowed_books"].append(record)
    books[book_id]["available"] = "No"
    return record


# 3a. Book status (detailed info)
@app.get("/book_status/<book_id>")
def book_status(book_id):
    if book_id not in books:
        return {"message": "Book not found"}, 404
    return books[book_id]


# 3b. Book enquiry (simple availability check)
@app.get("/book_enquiry/<book_id>")
def book_enquiry(book_id):
    if book_id not in books:
        return {"message": "Book not found"}, 404
    
    if books[book_id]["available"] == "Yes":
        return {"message": f"✅ Book {book_id} - {books[book_id]['name']} is available"}
    else:
        return {"message": f"❌ Book {book_id} - {books[book_id]['name']} is NOT available"}


# 4 & 5. Return book
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

            # Case: book missing
            if data.get("missing", False):
                book["fine"] = 500
                book["status"] = "Missing"
                return book

            # Case: late return
            if today > due_date:
                delay = (today - due_date).days
                book["fine"] = delay * 2

            book["status"] = "Returned"
            books[book_id]["available"] = "Yes"
            return book

    return {"message": "Book not found in student's borrowed list"}, 404


# Preload some books
books["B101"] = {"name": "Python Basics", "available": "Yes"}
books["B102"] = {"name": "Flask Web Dev", "available": "Yes"}
books["B103"] = {"name": "Data Science 101", "available": "Yes"}


if __name__ == "__main__":
    app.run(debug=True)
