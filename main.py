from flask import Flask, render_template, redirect, url_for, request, flash
import psycopg2
from datetime import datetime, date
import pymongo

app = Flask(__name__)
app.secret_key = 'F1askPy2000'

con = psycopg2.connect(host="localhost", database="Faculty_leave_management_DB", user="postgres", password="postgres")
cur = con.cursor()

client = pymongo.MongoClient('mongodb://127.0.0.1:27017/')
faculty_db = client['faculty']


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/Login')
def login():
    return render_template("login.html")


@app.route('/logout/<int:f_id>')
def logout(f_id):
    query = "delete from who_login where faculty_id = '{}'".format(f_id)
    cur.execute(query)
    con.commit()
    return redirect(url_for('login'))


@app.route('/profile/<int:f_id>')
def show_user_profile(f_id):
    query = "insert into who_login values('{}')".format(f_id)
    cur.execute(query)
    con.commit()
    query = """
                select * from faculty_details
                where faculty_id = '{}';
            """.format(f_id)
    cur.execute(query)
    faculty_info = cur.fetchone()
    content = []
    for _ in faculty_info:
        content.append(_)
    if content[5] == 'HoD':
        return render_template('hod_profile.html', content=content)
    elif content[5] == 'DFA':
        return render_template('dfa_profile.html', content=content)
    elif content[5] == 'Director':
        return render_template('director_profile.html', content=content)
    else:
        return render_template('profile.html', content=content)


@app.route('/login_validation', methods=['POST', 'GET'])
def login_validation():
    email = request.form.get('email')
    password = request.form.get('password')
    query = """ 
                select * from login_credentials
                where email = '{}' and password = '{}';
            """.format(email, password)
    cur.execute(query)
    user = cur.fetchall()
    if len(user) == 0:
        flash("Invalid credentials!", 'error')
        return redirect(url_for('login'))

    else:
        faculty_id = user[0][0]
        query = "select get_and_remove_notification('{}')".format(faculty_id)
        cur.execute(query)
        con.commit()
        msg = cur.fetchone()[0]
        flash_msg = None
        if msg == 'approved':
            flash_msg = 'Congratulations your leave has been granted!'
        elif msg == 'approved_by_hod':
            flash_msg = 'Your applications has been approved by the HoD and forwarded to the dean.'
        elif msg == 'rejected':
            flash_msg = 'Sorry your leave application was denied by the higher authorities.'
        elif msg == 'auto rejected':
            flash_msg = 'Sorry your leave application was automatically denied by the system due to no response.'
        elif msg == 'auto rejected2':
            flash_msg = 'Sorry your leave application was automatically denied by the system due to designation change. Please consider applying again through new route.'
        if flash_msg is not None:
            flash(flash_msg)
        return redirect(url_for('show_user_profile', f_id=faculty_id))


@app.route('/change_password/<int:f_id>')
def change_password(f_id):
    return render_template('change_password.html', f_id=f_id)


@app.route('/change_password_validation/<int:f_id>', methods=['POST', 'GET'])
def change_password_validation(f_id):
    old_key = request.form.get('old_password')
    new_key = request.form.get('new_password')
    confirm_key = request.form.get('confirm_new_password')
    query = """
                select password from login_credentials
                where faculty_id = '{}'
            """.format(f_id)
    cur.execute(query)
    curr_key = cur.fetchone()
    if new_key == confirm_key and old_key == curr_key[0] and old_key != new_key:
        query = """
                update login_credentials
                set password = '{}'
                where faculty_id = '{}'
                """.format(new_key, f_id)
        cur.execute(query)
        con.commit()
        flash("Password changed successfully!")
        return redirect(url_for('show_user_profile', f_id=f_id))
    else:
        flash("Use the correct old password and a new password different from the old one!")
        return render_template('change_password.html', f_id=f_id)


@app.route('/apply_validation/<int:f_id>')
def apply_validation(f_id):
    query = """
    select get_pending_application_id('{}')
    """.format(f_id)
    cur.execute(query)
    l_id = cur.fetchone()[0]
    if l_id == 0:
        return render_template('apply_page.html', f_id=f_id)
    else:
        flash("You already have one pending application!")
        return redirect(url_for('show_user_profile', f_id=f_id))


@app.route('/application_validation/<int:f_id>', methods=['POST', 'GET'])
def validate_application(f_id):
    query = """
            select leaves_available 
            from faculty_details
            where faculty_id = '{}'
            """.format(f_id)
    cur.execute(query)
    no_of_leaves_available = cur.fetchone()[0]
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    start_d = start_dt.date()
    end_d = end_dt.date()
    leaves_applied_for = (end_d - start_d).days + 1
    today = date.today()
    if end_d < start_d:
        flash('End date can not be less than the starting date!')
        return render_template('apply_page.html', f_id=f_id)
    elif no_of_leaves_available < leaves_applied_for:
        flash('You have only {} leave days, can not apply for more!'.format(no_of_leaves_available))
        return render_template('apply_page.html', f_id=f_id)
    # for retrospective leave
    elif start_d <= today:
        return render_template('retrospective_leave.html')
    else:
        query = "select get_leave_id()"
        cur.execute(query)
        leave_id = cur.fetchone()[0]
        body = request.form.get('body')
        from_date = start_dt
        to_date = end_dt
        content = str(body) + " - Leave applied from " + str(from_date.date()) + " to " + str(to_date.date())
        faculty_id = f_id
        date_applied = today
        status = 'pending'
        query = """
        insert into leave_details
        (leave_id, content, who_applied, date_applied, "from", "to", status)
        VALUES ('{}', '{}', '{}', '{}', '{}', '{}', '{}');
        """.format(leave_id, content, faculty_id, date_applied, from_date, to_date, status)
        cur.execute(query)
        con.commit()
        flash("Your leave application is in progress")
        return redirect(url_for('show_user_profile', f_id=f_id))


def construct_table(table):
    nice_table = []
    no_of_entries = len(table)
    for i in range(no_of_entries):
        row = []
        s = table[i][0].split(',')
        f_id = s[0][1:]
        content = s[1]
        date_applied = s[2][:-1]
        f_id = int(f_id)
        query = """select first_name, last_name, designation, department 
        from faculty_details 
        where faculty_id = '{}';
        """.format(f_id)
        cur.execute(query)
        info = cur.fetchone()
        name = info[0] + " " + info[1]
        position = info[2]
        dept = info[3]
        row.append(content)
        row.append(name)
        row.append(position)
        row.append(dept)
        row.append(date_applied)
        nice_table.append(row)
    return nice_table


@app.route('/application_record/who=<int:f_id>/what=<int:l_id>')
def application_record(f_id, l_id):
    # generate the application record using leave_details table and comment_details table
    query = "select get_application_record('{}')".format(l_id)
    cur.execute(query)
    table = cur.fetchall()
    nice_table = construct_table(table)
    return render_template('application_record.html', details=nice_table, f_id=f_id, l_id=l_id)


@app.route('/check_if_any_leave_in_process/<int:f_id>')
def check_if_any_leave_in_process(f_id):
    query = """
        select get_pending_application_id('{}')
        """.format(f_id)
    cur.execute(query)
    l_id = cur.fetchone()[0]
    if l_id == 0:
        flash('You do not have any leave application in process!')
        return redirect(url_for('show_user_profile', f_id=f_id))
    else:
        return redirect(url_for('application_record', f_id=f_id, l_id=l_id))


@app.route('/view_details/who=<int:_id>/what=<int:l_id>')
def view_details(_id, l_id):
    return redirect(url_for('application_record', f_id=_id, l_id=l_id))


def construct_table2(table, hod_id):
    nice_table = []
    no_of_entries = len(table)
    for i in range(no_of_entries):
        row = []
        s = table[i][0].split(',')
        leave_id = s[0][1:]
        who_applied = s[1]
        date_applied = s[2]
        status = s[3][:-1]
        query = """select first_name, last_name, designation, department 
           from faculty_details 
           where faculty_id = '{}';
           """.format(who_applied)
        cur.execute(query)
        info = cur.fetchone()
        name = info[0] + " " + info[1]
        row.append(leave_id)
        row.append(name)
        row.append(date_applied)
        row.append(status)
        row.append(int(who_applied))
        row.append(int(hod_id))
        nice_table.append(row)
    return nice_table


@app.route('/check_leave_requests_for_hod/<int:f_id>')
def collect_all_requests_for_hod(f_id):
    query = "select get_all_req('{}')".format(f_id)
    cur.execute(query)
    table = cur.fetchall()
    if len(table) == 0:
        flash('You do not have any leave requests yet!')
        return redirect(url_for('show_user_profile', f_id=f_id))
    nice_table = construct_table2(table, f_id)
    return render_template('leave_req_for_hod.html', details=nice_table)


@app.route('/check_leave_requests_for_dfa/<int:f_id>')
def collect_all_requests_for_dfa(f_id):
    query = "select get_all_req('{}')".format(f_id)
    cur.execute(query)
    table = cur.fetchall()
    if len(table) == 0:
        flash('You do not have any leave requests yet!')
        return redirect(url_for('show_user_profile', f_id=f_id))
    nice_table = construct_table2(table, f_id)
    return render_template('leave_req_for_dfa.html', details=nice_table)


@app.route('/check_leave_requests_for_director/<int:f_id>')
def collect_all_requests_for_director(f_id):
    query = "select get_all_req_for_director()"
    cur.execute(query)
    table = cur.fetchall()
    if len(table) == 0:
        flash('You do not have any leave requests yet!')
        return redirect(url_for('show_user_profile', f_id=f_id))
    nice_table = construct_table2(table, f_id)
    return render_template('leave_req_for_dfa.html', details=nice_table)


@app.route('/approved_by_hod/id = <int:hod_id>/on leave = <int:leave_id>')
def approved_by_hod(hod_id, leave_id):
    query = "select get_comm_id()"
    cur.execute(query)
    com_id = cur.fetchone()[0]
    today = date.today()
    query = "insert into comment_details values('{}', '{}', '{}', '{}', '{}')".\
        format(com_id, leave_id, hod_id, 'Approved by HoD and forwarded to the Dean', today)
    cur.execute(query)
    con.commit()
    query = "update leave_details set status = '{}' where leave_id = '{}'".format('approved_by_hod', leave_id)
    cur.execute(query)
    con.commit()
    flash('Approval message has been sent to the concerned faculty!', category='success')
    return redirect(url_for('show_user_profile', f_id=hod_id))


@app.route('/approved/id = <int:_id>/on leave = <int:leave_id>')
def approved(_id, leave_id):
    query = "select get_no_of_leave_days('{}')".format(leave_id)
    cur.execute(query)
    days_taken = cur.fetchone()[0]
    query = "select update_leave_available('{}', '{}')".format(leave_id, days_taken)
    cur.execute(query)
    con.commit()
    query = "update leave_details set status = '{}' where leave_id = '{}'".format('approved', leave_id)
    cur.execute(query)
    con.commit()
    flash('Approval message has been sent to the concerned faculty!', category='success')
    return redirect(url_for('show_user_profile', f_id=_id))


@app.route('/rejected/id = <int:_id>/on leave = <int:leave_id>')
def rejected(_id, leave_id):
    query = "update leave_details set status = '{}' where leave_id = '{}'".format('rejected', leave_id)
    cur.execute(query)
    con.commit()
    flash('Rejection message has been sent to the concerned faculty!', category='error')
    return redirect(url_for('show_user_profile', f_id=_id))


@app.route('/add_comment_now/<int:f_id>/<int:l_id>',  methods=['POST', 'GET'])
def add_comment_now(f_id, l_id):
    query = "select get_comm_id()"
    cur.execute(query)
    com_id = cur.fetchone()[0]
    body = request.form.get('body')
    today = date.today()
    query = "insert into comment_details values('{}', '{}', '{}', '{}', '{}')".format(com_id, l_id, f_id, body, today)
    cur.execute(query)
    con.commit()
    return redirect(url_for('application_record', f_id=f_id, l_id=l_id))


@app.route('/add_comment/<int:f_id>/<int:l_id>')
def add_comment(f_id, l_id):
    return render_template('write_comment.html', f_id=f_id, l_id=l_id)


@app.route('/safely_go_back/who=<int:f_id>/what<int:l_id>')
def safely_go_back(f_id, l_id):
    query = "select who_applied from leave_details where leave_id = '{}'".format(l_id)
    cur.execute(query)
    who_applied = cur.fetchone()[0]
    query = "select designation from faculty_details where faculty_id = '{}'".format(f_id)
    cur.execute(query)
    position = cur.fetchone()[0]
    if f_id == who_applied:
        return redirect(url_for('show_user_profile', f_id=f_id))
    else:
        if position == 'HoD':
            return redirect(url_for('collect_all_requests_for_hod', f_id=f_id))
        elif position == 'DFA':
            return redirect(url_for('collect_all_requests_for_dfa', f_id=f_id))
        elif position == 'Director':
            return redirect(url_for('collect_all_requests_for_director', f_id=f_id))


def construct_table3(table):
    nice_table = []
    no_of_entries = len(table)
    for i in range(no_of_entries):
        row = []
        s = table[i][0].split(',')
        s_no = s[0][1:]
        leave_id = s[1]
        date_applied = s[2]
        verdict = s[3]
        date_of_verdict = s[4][:-1]
        row.append(s_no)
        row.append(leave_id)
        row.append(date_applied)
        row.append(verdict)
        row.append(date_of_verdict)
        nice_table.append(row)
    return nice_table


@app.route('/view_previous_applications/<int:f_id>')
def view_previous_applications(f_id):
    query = "select get_all_previous_leaves('{}')".format(f_id)
    cur.execute(query)
    table = cur.fetchall()
    if len(table) == 0:
        flash('You do not have any leave application that is finalized!')
        return redirect(url_for('show_user_profile', f_id=f_id))
    nice_table = construct_table3(table)
    return render_template('prev_leave_details.html', details=nice_table, f_id=f_id)


@app.route('/final_record/<int:l_id>')
def show_finalized_record(l_id):
    query = "select get_old_application_record('{}')".format(l_id)
    cur.execute(query)
    table = cur.fetchall()
    query = "select verdict from old_leave_details where leave_id='{}'".format(l_id)
    cur.execute(query)
    verdict = cur.fetchone()[0]
    if verdict == 'auto rejected2':
        verdict = 'auto rejected by the system due to designation change'
    nice_table = construct_table(table)
    return render_template('final_application_record.html', details=nice_table, verdict=verdict)


def auto_reject_applications():
    query = "select auto_reject_applications()"
    cur.execute(query)
    con.commit()
    return None


def construct_table4(table):
    nice_table = []
    no_of_entries = len(table)
    for i in range(no_of_entries):
        row = []
        s = table[i][0].split(',')
        f_id = s[0][1:]
        f_name = s[1]
        l_name = s[2]
        name = f_name + " " + l_name
        dept = s[3][:-1]
        row.append(f_id)
        row.append(name)
        row.append(dept)
        nice_table.append(row)
    return nice_table


def construct_table5(table):
    nice_table = []
    no_of_entries = len(table)
    for i in range(no_of_entries):
        row = []
        s = table[i][0].split(',')
        f_id = s[0][1:]
        f_name = s[1]
        l_name = s[2][:-1]
        name = f_name + " " + l_name
        row.append(f_id)
        row.append(name)
        nice_table.append(row)
    return nice_table


@app.route('/change_faculty_positions')
def change_faculty():

    query = "select get_candidates_for_dfa()"
    cur.execute(query)
    table1 = cur.fetchall()
    nice_table1 = construct_table4(table1)

    query = "select get_candidates_for_hod('{}')".format('CSE')
    cur.execute(query)
    table2 = cur.fetchall()
    nice_table2 = construct_table5(table2)

    query = "select get_candidates_for_hod('{}')".format('EE')
    cur.execute(query)
    table3 = cur.fetchall()
    nice_table3 = construct_table5(table3)

    query = "select get_candidates_for_hod('{}')".format('ME')
    cur.execute(query)
    table4 = cur.fetchall()
    nice_table4 = construct_table5(table4)

    return render_template('change_faculty.html', list1=nice_table1, list2=nice_table2, list3=nice_table3, list4=nice_table4)


@app.route('/confirm_change_dfa', methods=['POST', 'GET'])
def confirm_change_dfa():
    query = "update faculty_details set designation = '{}' where designation = '{}'".format('faculty', 'DFA')
    cur.execute(query)
    con.commit()
    new_dfa_id = request.form.get('new_dfa')
    new_dfa_id = int(new_dfa_id)
    query = "update faculty_details set designation = '{}' where faculty_id = '{}'".format('DFA', new_dfa_id)
    cur.execute(query)
    con.commit()
    flash('New Dean FAA has been appointed!', category="success")
    return redirect(url_for('show_user_profile', f_id=4))


@app.route('/confirm_change_hod', methods=['POST', 'GET'])
def confirm_change_hod():
    new_id = request.form.get('new_hod')
    query = "select department from faculty_details where faculty_id = '{}'".format(new_id)
    cur.execute(query)
    dept = cur.fetchone()[0]
    query = "update faculty_details set designation = '{}' where designation = '{}' and department = '{}'".format('faculty', 'HoD', dept)
    cur.execute(query)
    con.commit()
    query = "update faculty_details set designation = '{}' where faculty_id = '{}'".format('HoD', new_id)
    cur.execute(query)
    con.commit()
    flash("New HoD(s) has been appointed!", category="success")
    return redirect(url_for('show_user_profile', f_id=4))


@app.route('/detailed_profile/<int:f_id>/<name>')
def show_detailed_profile(f_id, name):
    query = "select faculty_id from who_login where faculty_id = '{}'".format(f_id)
    cur.execute(query)
    show = True
    if cur.fetchone() is None:
        show = False
    _filter = {"f_id": f_id}
    names = name.split('-')
    name = names[0] + " " + names[1]
    doc = faculty_db.profiles.find_one(_filter)
    background = doc["background"]
    courses = doc['courses']
    publications = doc['publications']
    return render_template('detailed_info.html', show=show, f_id=f_id, name=name, background=background, courses=courses, publications=publications)


def get_name(f_id):
    query = "select first_name, last_name from faculty_details where faculty_id = '{}'".format(f_id)
    cur.execute(query)
    f_name = cur.fetchone()[0]
    query = "select last_name from faculty_details where faculty_id = '{}'".format(f_id)
    cur.execute(query)
    l_name = cur.fetchone()[0]
    name = f_name + "-" + l_name
    return name


@app.route('/more_info/<int:f_id>')
def more_info(f_id):
    name = get_name(f_id)
    return redirect(url_for('show_detailed_profile', f_id=f_id, name=name))


@app.route('/delete_course/<int:f_id>/<course_id>')
def remove_course(f_id, course_id):
    name = get_name(f_id)
    faculty_db.profiles.update(
        {'f_id': f_id},
        {'$pull': {'courses': {'c_id': course_id}}}
    )
    return redirect(url_for('show_detailed_profile', f_id=f_id, name=name))


@app.route('/delete_publication/<int:f_id>/<title>')
def remove_publication(f_id, title):
    name = get_name(f_id)
    faculty_db.profiles.update(
        {'f_id': f_id},
        {'$pull': {'publications': {'title': title}}}
    )
    return redirect(url_for('show_detailed_profile', f_id=f_id, name=name))


@app.route('/add_course/<int:f_id>',  methods=['POST', 'GET'])
def add_course(f_id):
    course_id = request.form.get('course_id')
    course_name = request.form.get('course_name')
    faculty_db.profiles.update(
        {'f_id': f_id},
        {'$push': {'courses': {'c_id': course_id, 'c_name': course_name}}}
    )
    name = get_name(f_id)
    return redirect(url_for('show_detailed_profile', f_id=f_id, name=name))


@app.route('/open_add_course_form/<int:f_id>')
def open_course_form(f_id):
    return render_template('course_form.html', f_id=f_id)


@app.route('/add_publication/<int:f_id>',  methods=['POST', 'GET'])
def add_publication(f_id):
    title = request.form.get('title')
    description = request.form.get('description')
    faculty_db.profiles.update(
        {'f_id': f_id},
        {'$push': {'publications': {'title': title, 'description': description}}}
    )
    name = get_name(f_id)
    return redirect(url_for('show_detailed_profile', f_id=f_id, name=name))


@app.route('/open_add_publication_form/<int:f_id>')
def open_publication_form(f_id):
    return render_template('publication_form.html', f_id=f_id)


@app.route('/edit_background/<int:f_id>', methods=['POST', 'GET'])
def edit_background(f_id):
    background = request.form.get('background')
    faculty_db.profiles.update(
        {'f_id': f_id},
        {'$set': {'background': background}}
    )
    return redirect(url_for('show_detailed_profile', f_id=f_id, name=get_name(f_id)))


@app.route('/open_edit_background/<int:f_id>')
def open_edit_background_form(f_id):
    _filter = {'f_id': f_id}
    doc = faculty_db.profiles.find_one(_filter)
    background = doc["background"]
    return render_template('background_form.html', f_id=f_id, background=background)


if __name__ == '__main__':
    auto_reject_applications()
    app.run(debug=True)


cur.close()
con.close()
