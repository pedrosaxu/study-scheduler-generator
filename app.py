#!/usr/bin/env python
from flask import Flask, request, send_file, render_template_string
import io
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event

app = Flask(__name__)

# HTML form template with collapsible text area for input
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Study Schedule Generator</title>
    <!-- Include Bootstrap CSS -->
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <script>
    function toggleInputBox() {
        var x = document.getElementById("inputBox");
        if (x.style.display === "none") {
            x.style.display = "block";
        } else {
            x.style.display = "none";
        }
    }
    </script>
</head>
<body>
    <div class="container mt-5">
        <h2>Generate Study Schedule</h2>
        <form method="post">
            <div class="form-group">
                <label>Start Date (YYYY-MM-DD):</label>
                <input type="text" class="form-control" name="start_date" required>
            </div>
            <div class="form-group">
                <label>Study Days (1=Monday, ..., 7=Sunday), separated by commas:</label>
                <input type="text" class="form-control" name="study_days" required>
            </div>
            <div class="form-group">
                <label>Start Time (HH:MM):</label>
                <input type="text" class="form-control" name="start_time" required>
            </div>
            <div class="form-group">
                <label>Daily Study Limit Hours:</label>
                <input type="number" class="form-control" name="daily_study_limit_hours" required>
            </div>
            <div class="form-group">
                <label>Multiplier:</label>
                <input type="text" class="form-control" name="multiplier" required>
            </div>
            <button type="button" class="btn btn-info mb-3" onclick="toggleInputBox()">Toggle Class Input Box</button>
            <div id="inputBox" class="form-group" style="display:none;">
                <label>Class Input:</label>
                <textarea class="form-control" name="class_input" rows="10"></textarea>
            </div>
            <input type="submit" class="btn btn-primary" value="Generate Schedule">
        </form>
    </div>
    <!-- Include Bootstrap JS and its dependencies -->
    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.2/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def form():
    return render_template_string(HTML_TEMPLATE)

@app.route('/', methods=['POST'])
def generate_schedule():
    start_date_str = request.form['start_date']
    study_days_input = request.form['study_days']
    start_time_str = request.form['start_time']
    daily_study_limit_hours = int(request.form['daily_study_limit_hours'])
    multiplier = float(request.form['multiplier'])
    class_input = request.form['class_input']

    classes = parse_class_input(class_input)
    adjusted_classes = apply_multiplier(classes, multiplier)

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    study_days = [int(day) for day in study_days_input.split(',')]
    study_schedule = schedule_classes(adjusted_classes, start_date, study_days, daily_study_limit_hours)

    ical_data = create_calendar_events(study_schedule, start_time_str, 'America/Sao_Paulo', daily_study_limit_hours)

    # Sending the file back to the client
    ical_file = io.BytesIO(ical_data)
    ical_file.seek(0)
    return send_file(ical_file, as_attachment=True, download_name='study_schedule.ics', mimetype='text/calendar')

def parse_class_input(class_input):
    """Parses class input from a text area and returns a list of classes."""
    classes = []
    lines = class_input.split('\n')

    i = 0
    while i < len(lines):
        status = lines[i].strip()
        if i + 2 < len(lines):
            subject = lines[i + 1].strip()
            duration_line = lines[i + 2].strip()
            if 'min' in duration_line:
                duration_str = duration_line.replace('min', '')
                try:
                    duration = int(duration_str)
                    classes.append([status, subject, duration])
                    i += 3
                except ValueError:
                    i += 1  # Skip the problematic line
            else:
                i += 1
        else:
            break
    return classes


def apply_multiplier(classes, multiplier):
    """Applies the multiplier to class durations."""
    return [[cls[0], cls[1], cls[2] * multiplier] for cls in classes]

def schedule_classes(classes, start_date, study_days, daily_study_limit_hours):
    """Schedules classes into daily study blocks."""
    study_schedule = {}
    daily_study_limit_minutes = daily_study_limit_hours * 60
    current_date = start_date
    time_left = daily_study_limit_minutes

    for cls in classes:
        while cls[2] > 0:
            if current_date.weekday() in study_days:
                if time_left >= cls[2]:
                    if current_date not in study_schedule:
                        study_schedule[current_date] = []
                    study_schedule[current_date].append(cls)
                    time_left -= cls[2]
                    cls[2] = 0
                else:
                    if current_date not in study_schedule:
                        study_schedule[current_date] = []
                    split_class = cls[:]
                    split_class[2] = time_left
                    study_schedule[current_date].append(split_class)
                    cls[2] -= time_left
                    time_left = 0
            if time_left == 0 or current_date.weekday() not in study_days:
                current_date += timedelta(days=1)
                time_left = daily_study_limit_minutes

    return study_schedule

def create_calendar_events(study_schedule, start_time_str, timezone, daily_study_limit_hours):
    """Creates calendar events for each study block."""
    cal = Calendar()
    cal.add('prodid', '-//Study Schedule Calendar//mxm.dk//')
    cal.add('version', '2.0')
    local_tz = pytz.timezone(timezone)

    for day, classes in study_schedule.items():
        start_datetime = datetime.combine(day, datetime.strptime(start_time_str, '%H:%M').time())
        start_datetime = local_tz.localize(start_datetime)
        end_datetime = start_datetime + timedelta(minutes=daily_study_limit_hours*60)

        event = Event()
        event.add('summary', f"Study Block {day.strftime('%Y-%m-%d')}")
        event.add('dtstart', start_datetime)
        event.add('dtend', end_datetime)
        event.add('description', "Classes today:\n" + '\n'.join(cls[1] for cls in classes))
        cal.add_component(event)

    return cal.to_ical()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
