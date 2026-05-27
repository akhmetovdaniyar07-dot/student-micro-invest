#include <iostream>
#include <vector>
#include <string>
#include <iomanip>
#include <algorithm>
#include <limits>
#include "crow_all.h"

using namespace std;

// Студенттің жеке деректерін және бағалау логикасын басқаратын класс
class Student {
private:
    string name;
    vector<double> grades;
    double average;
    string letterGrade;
    double gpa;
    int traditionalGrade;

    void calculateGrades() {
        if (grades.empty()) {
            average = 0;
            return;
        }
        double sum = 0;
        for (double g : grades) sum += g;
        average = sum / grades.size();

        // Конвертация логикасы (SRS бойынша)
        if (average >= 90) { letterGrade = "A"; gpa = 4.0; traditionalGrade = 5; }
        else if (average >= 80) { letterGrade = "B"; gpa = 3.0; traditionalGrade = 4; }
        else if (average >= 70) { letterGrade = "C"; gpa = 2.0; traditionalGrade = 3; }
        else if (average >= 60) { letterGrade = "D"; gpa = 1.0; traditionalGrade = 3; }
        else { letterGrade = "F"; gpa = 0.0; traditionalGrade = 2; }
    }

public:
    Student(string n, vector<double> g) : name(n), grades(g) {
        calculateGrades();
    }

    // Веб үшін JSON форматына айналдыру
    crow::json::wvalue to_json() const {
        crow::json::wvalue x;
        x["name"] = name;
        x["average"] = average;
        x["letterGrade"] = letterGrade;
        x["gpa"] = gpa;
        x["traditionalGrade"] = traditionalGrade;
        return x;
    }

    string getName() const { return name; }
    double getAverage() const { return average; }
    string getLetterGrade() const { return letterGrade; }
    double getGPA() const { return gpa; }
    int getTraditional() const { return traditionalGrade; }

    void displayRow(int rank) const {
        cout << left << setw(6) << rank
             << setw(20) << name
             << setw(12) << fixed << setprecision(2) << average << "%"
             << setw(15) << letterGrade
             << setw(8) << gpa
             << setw(10) << traditionalGrade << endl;
    }
};

// Жүйенің негізгі басқару модулі
class GradeSystem {
private:
    vector<Student> students;

    // Сандық енгізуді тексеру (Validation)
    double getValidScore() {
        double score;
        while (true) {
            if (cin >> score && score >= 0 && score <= 100) {
                return score;
            } else {
                cout << "Қате! 0-100 аралығындағы санды енгізіңіз: ";
                cin.clear();
                cin.ignore(numeric_limits<streamsize>::max(), '\n');
            }
        }
    }

public:
    void addStudent() {
        string name;
        int count;
        cout << "Студенттің аты-жөні: ";
        cin.ignore();
        getline(cin, name);
        cout << "Бағалар саны: ";
        while (!(cin >> count) || count <= 0) {
            cout << "Оң сан енгізіңіз: ";
            cin.clear();
            cin.ignore(numeric_limits<streamsize>::max(), '\n');
        }

        vector<double> scores;
        for (int i = 0; i < count; ++i) {
            cout << i + 1 << "-бағаны енгізіңіз (%): ";
            scores.push_back(getValidScore());
        }
        students.emplace_back(name, scores);
        cout << "\nСтудент сәтті қосылды!\n";
    }

    void displayTable(bool sorted = false) {
        if (students.empty()) {
            cout << "\nТізім бос! Алдымен студент қосыңыз.\n";
            return;
        }

        if (sorted) {
            sort(students.begin(), students.end(), [](const Student& a, const Student& b) {
                return a.getAverage() > b.getAverage();
            });
        }

        cout << "\n" << string(70, '-') << endl;
        cout << left << setw(6) << "Реті" << setw(20) << "Аты-жөні" << setw(12) << "Пайыз (%)" 
             << setw(15) << "Әріптік баға" << setw(8) << "GPA" << setw(10) << "Дәстүрлі" << endl;
        cout << string(70, '-') << endl;

        for (size_t i = 0; i < students.size(); ++i) {
            students[i].displayRow(i + 1);
        }
        cout << string(70, '-') << endl;

        double totalAvg = 0;
        for (const auto& s : students) totalAvg += s.getAverage();
        cout << "Топтың жалпы орташа көрсеткіші: " << fixed << setprecision(2) << totalAvg / students.size() << "%\n";
    }

    // Топтың жалпы орташа пайызын есептеу
    double getGroupAverage() {
        if (students.empty()) return 0;
        double total = 0;
        for (const auto& s : students) total += s.getAverage();
        return total / students.size();
    }

    // Тест үшін студенттерді қолмен қосу функциясы
    void addStudentManual(string n, vector<double> g) {
        students.emplace_back(n, g);
    }

    // Веб үшін барлық студенттердің тізімін алу
    vector<crow::json::wvalue> getStudentsJson() {
        vector<crow::json::wvalue> res;
        for (const auto& s : students) {
            res.push_back(s.to_json());
        }
        return res;
    }

    // Сайттан келген JSON дерегі арқылы студент қосу
    void addFromJson(const crow::json::rvalue& x) {
        if (!x.has("name") || !x.has("grades")) return;
        
        string n = x["name"].s();
        vector<double> g;
        for (const auto& grade : x["grades"]) {
            g.push_back(grade.d());
        }
        students.emplace_back(n, g);
    }

    // Рейтинг бойынша сұрыптау (Кему ретімен)
    void sortByRank() {
        sort(students.begin(), students.end(), [](const Student& a, const Student& b) {
            return a.getAverage() > b.getAverage();
        });
    }
};

int main() {
    crow::SimpleApp app;
    GradeSystem system;

    // Тест үшін бірнеше студент қосамыз
    system.addStudentManual("Асан Әлиев", {95, 98, 92});
    system.addStudentManual("Марат Сұлтанов", {80, 85, 82});

    // API бағытын (route) анықтаймыз. Бұл жерде 404 болмауы үшін мекенжай нақты жазылуы керек.
    CROW_ROUTE(app, "/api/students")
    ([&system](){
        system.sortByRank(); // Деректерді жібермес бұрын сұрыптаймыз
        crow::json::wvalue x;
        x["students"] = std::move(system.getStudentsJson());
        x["groupAverage"] = system.getGroupAverage();
        
        // CORS мәселесін шешу үшін header қосамыз
        crow::response res(x);
        res.add_header("Access-Control-Allow-Origin", "*");
        return res;
    });

    // Жаңа студент қосуға арналған POST route
    CROW_ROUTE(app, "/api/add").methods(crow::HTTPMethod::POST)
    ([&system](const crow::request& req){
        auto x = crow::json::load(req.body);
        if (!x || !x.has("name") || !x.has("grades")) {
            return crow::response(400, "Қате деректер");
        }
        
        system.addFromJson(x);
        crow::response res(200, "Студент қосылды");
        res.add_header("Access-Control-Allow-Origin", "*");
        return res;
    });

    cout << "Сервер http://localhost:18080 мекенжайында қосылды..." << endl;
    app.port(18080).multithreaded().run();
}