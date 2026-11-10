"""Exercise the real PostgreSQL storage in a temporary, isolated schema.

DATABASE_URL must be set by the caller. Never writes synthetic responses to public.
"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg import sql


def main():
    url = os.environ['DATABASE_URL']
    schema = 'migration_test_' + uuid.uuid4().hex
    previous = os.environ.get('PGOPTIONS')
    print('Creating isolated PostgreSQL test schema', flush=True)
    with psycopg.connect(url, sslmode='require', connect_timeout=10) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    os.environ['PGOPTIONS'] = f'-c search_path={schema}'
    try:
        import database
        import metrics
        import user_login
        import app
        from db_connection import connect, export_records
        from survey_engine import build_survey_view_model, save_survey_submission, validate_submission
        from werkzeug.datastructures import MultiDict

        database.init_database()
        print('Schema initialized', flush=True)
        assert user_login.user_registration('TEST_registered', 'Test-only-password!',
            'test@example.invalid', '+15555550123', 'TEST')[0]
        assert not user_login.user_registration('TEST_registered', 'Test-only-password!',
            'test@example.invalid', '+15555550123', 'TEST')[0]
        assert user_login.verifying_login('TEST_registered', 'Test-only-password!')[0]
        guest = database.create_guest_session(True)
        assert database.is_guest_username(guest)

        for participant in ['TEST_registered', guest]:
            print('Testing participant storage', flush=True)
            for phase in ['pre', 'post']:
                model = build_survey_view_model('unused.db', participant, phase)
                form = MultiDict({'consent_response': 'yes'})
                for section in model['sections']:
                    questions = list(section.get('questions', []))
                    for subsection in section.get('subsections', []):
                        questions.extend(subsection.get('questions', []))
                    for q in questions:
                        if q['type'] == 'numeric': value = '72'
                        elif q['type'] == 'openText': value = 'TEST migration verification'
                        elif q.get('scale'): value = str(q['scale']['max'])
                        else: value = q['options'][0]
                        form.add(q['fieldName'], value)
                answers, error = validate_submission(form, model)
                assert error is None, error
                save_survey_submission('unused.db', participant, phase, model, answers)
                save_survey_submission('unused.db', participant, phase, model, answers)
            metrics.log_scenario_attempt(participant, 'email', 'desktop', 'scam', 'scam',
                True, 2, duration_seconds=30, indicators_found=['TEST clue'])
            metrics.update_module_progress(participant, 'module1')
            for read in [metrics.get_user_performance, metrics.get_module_progress,
                         metrics.get_attempt_history, metrics.get_survey_comparison,
                         metrics.get_learning_metrics]:
                assert read(participant)['success'], read.__name__

        app.app.config.update(TESTING=True, SECRET_KEY='test-only')
        with app.app.test_client() as client:
            with client.session_transaction() as session:
                session['username'] = guest
                session['is_guest'] = True
            assert client.get('/dashboard').status_code == 200
            assert client.get('/reset_presurvey').status_code == 404
        with connect() as connection:
            assert connection.execute('SELECT COUNT(*) FROM pre_survey').fetchone()[0] == 2
            assert connection.execute('SELECT COUNT(*) FROM post_survey').fetchone()[0] == 2
        assert len(export_records()['guest_sessions']) == 1
        print('PASS: PostgreSQL registration, login, guest, pre/post surveys, repeat submissions, training, metrics, dashboard, export')
    finally:
        if previous is None: os.environ.pop('PGOPTIONS', None)
        else: os.environ['PGOPTIONS'] = previous
        with psycopg.connect(url, sslmode='require', connect_timeout=10) as admin:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


if __name__ == '__main__':
    main()
