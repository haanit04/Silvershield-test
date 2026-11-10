"""
SilverShield Metrics Module - Isolated metrics collection and assessment tracking

This module handles all Assessment & Metrics functionality (Goal 2):
- Scenario attempt logging
- Critical indicator tracking
- Performance aggregation
- Module progress monitoring
- Survey data collection
"""

import sqlite3
from db_connection import connect as db_connect, using_postgres, insert_id
import json
import time
from datetime import datetime, timedelta

DB_PATH = "silvershieldDatabase.db"
REQUIRED_ATTEMPTS_PER_SIMULATION = 5


def _connect():
    """Return a SQLite connection with a retry timeout to avoid 'database is locked' errors."""
    return db_connect(DB_PATH, timeout=10)


def log_scenario_attempt(username, scenario_type, platform, user_choice, correct_answer,
                         is_correct, difficulty_level, ai_feedback=None, start_time=None,
                         duration_seconds=None, message=None, indicators_found=None):
    """
    Log a user's attempt on a scenario.
    
    Args:
        username: User's username
        scenario_type: Type of scenario (email, internet, sms, call, web)
        platform: Platform (desktop or mobile)
        user_choice: What the user selected
        correct_answer: Correct answer for the scenario
        is_correct: Boolean - was the answer correct?
        difficulty_level: Current difficulty level
        ai_feedback: JSON string with AI feedback
        start_time: Timestamp when scenario started (in seconds since epoch)
        duration_seconds: Optional explicit duration; if not provided, calculated from start_time
        message: The scenario content/message the user saw
    """
    # Calculate duration if start_time provided and duration not explicit
    if duration_seconds is None and start_time:
        duration_seconds = int(time.time() - start_time)
    
    with _connect() as conn:
        cursor = conn.cursor()
        
        # Set end_time to current time
        end_time_str = datetime.now().isoformat()
        
        # Calculate start_time: if we have duration_seconds, work backwards from end_time
        if start_time:
            # start_time provided as epoch (seconds)
            start_time_str = datetime.fromtimestamp(start_time).isoformat()
        elif duration_seconds:
            # Calculate start_time by subtracting duration from end_time
            end_time_obj = datetime.now()
            start_time_obj = end_time_obj - timedelta(seconds=duration_seconds)
            start_time_str = start_time_obj.isoformat()
        else:
            # No timing info, set start_time to end_time
            start_time_str = end_time_str
        
        scenario_attempt_id = insert_id(cursor, """
            INSERT INTO scenario_attempts 
            (username, scenario_type, scenario_platform, user_choice, correct_answer, 
             is_correct, difficulty_level, ai_feedback, start_time, end_time, duration_seconds, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, scenario_type, platform, user_choice, correct_answer, is_correct, 
              difficulty_level, ai_feedback, start_time_str, end_time_str, duration_seconds, message))

        # Treat provided clues as critical indicators identified in this attempt.
        indicator_list = [indicator for indicator in (indicators_found or []) if indicator]
        indicator_count = len(indicator_list)

        if indicator_list:
            for indicator in indicator_list:
                cursor.execute("""
                    INSERT INTO critical_indicators
                    (username, scenario_attempt_id, scenario_type, indicator_name, identified)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, scenario_attempt_id, scenario_type, indicator, True))
        
        # Update performance summary in same transaction to avoid nested connections
        cursor.execute("""
            SELECT total_attempts, correct_attempts, average_duration_seconds, total_indicators_identified
            FROM performance_summary
            WHERE username = ? AND scenario_type = ?
        """, (username, scenario_type))
        
        row = cursor.fetchone()
        
        if row:
            total_attempts = row[0] + 1
            correct_attempts = row[1] + (1 if is_correct else 0)
            old_avg = row[2]
            total_indicators = row[3] + indicator_count
            
            if old_avg and duration_seconds:
                new_duration = (old_avg * (total_attempts - 1) + duration_seconds) / total_attempts
            else:
                new_duration = duration_seconds if duration_seconds else 0
            
            success_rate = (correct_attempts / total_attempts) * 100
            
            cursor.execute("""
                UPDATE performance_summary
                SET total_attempts = ?, correct_attempts = ?, success_rate = ?,
                    average_duration_seconds = ?, total_indicators_identified = ?
                WHERE username = ? AND scenario_type = ?
            """, (total_attempts, correct_attempts, success_rate, new_duration,
                  total_indicators, username, scenario_type))
        else:
            total_attempts = 1
            correct_attempts = 1 if is_correct else 0
            success_rate = (correct_attempts / total_attempts) * 100
            
            cursor.execute("""
                INSERT INTO performance_summary 
                (username, scenario_type, total_attempts, correct_attempts, success_rate,
                 average_duration_seconds, total_indicators_identified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username, scenario_type, total_attempts, correct_attempts, success_rate,
                  duration_seconds if duration_seconds else 0, indicator_count))
        
        conn.commit()


def log_critical_indicators(username, scenario_attempt_id, scenario_type, indicators_found):
    """
    Log critical indicators identified by user.
    
    Args:
        username: User's username
        scenario_attempt_id: ID of the scenario attempt
        scenario_type: Type of scenario
        indicators_found: List of indicators identified
    """
    with _connect() as conn:
        cursor = conn.cursor()
        for indicator in indicators_found:
            cursor.execute("""
                INSERT INTO critical_indicators 
                (username, scenario_attempt_id, scenario_type, indicator_name, identified)
                VALUES (?, ?, ?, ?, ?)
            """, (username, scenario_attempt_id, scenario_type, indicator, True))
        
        conn.commit()


def update_module_progress(username, module_name, scenarios_completed=None):
    """
    Update module progress for a user.
    """
    with _connect() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT scenarios_completed, total_scenarios FROM module_progress
            WHERE username = ? AND module_name = ?
        """, (username, module_name))
        
        row = cursor.fetchone()
        
        if row:
            current_completed = row[0] or 0
            requested_count = (current_completed + 1) if scenarios_completed is None else scenarios_completed
            new_count = min(max(0, requested_count), REQUIRED_ATTEMPTS_PER_SIMULATION)
            cursor.execute("""
                UPDATE module_progress
                SET scenarios_completed = ?, total_scenarios = ?, last_accessed = CURRENT_TIMESTAMP
                WHERE username = ? AND module_name = ?
            """, (new_count, REQUIRED_ATTEMPTS_PER_SIMULATION, username, module_name))
        else:
            initial_count = 1 if scenarios_completed is None else min(max(0, scenarios_completed), REQUIRED_ATTEMPTS_PER_SIMULATION)
            cursor.execute("""
                INSERT INTO module_progress 
                (username, module_name, scenarios_completed, total_scenarios, last_accessed)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (username, module_name, initial_count, REQUIRED_ATTEMPTS_PER_SIMULATION))
        
        conn.commit()


def get_user_performance(username):
    """
    Get overall performance summary for a user across all scenario types.
    """
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT scenario_type, total_attempts, correct_attempts, success_rate, 
                       average_duration_seconds, total_indicators_identified
                FROM performance_summary
                WHERE username = ?
                ORDER BY scenario_type
            """, (username,))
            
            performance_data = [
                {
                    "scenario_type": row[0],
                    "total_attempts": row[1],
                    "correct_attempts": row[2],
                    "success_rate": round(row[3], 2),
                    "avg_duration_seconds": round(row[4], 2) if row[4] else 0,
                    "critical_indicators_found": row[5]
                }
                for row in cursor.fetchall()
            ]
            
            return {"success": True, "data": performance_data}
    except Exception as e:
        print(f"Error fetching performance: {e}")
        return {"success": False, "error": str(e)}


def get_module_progress(username):
    """
    Get module completion progress for a user.
    """
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT module_name, scenarios_completed, total_scenarios, 
                       ROUND((scenarios_completed * 100.0 / total_scenarios), 1) as completion_pct,
                       last_accessed
                FROM module_progress
                WHERE username = ?
                ORDER BY last_accessed DESC
            """, (username,))
            
            modules = [
                {
                    "module_name": row[0],
                    "completed": min(row[1], row[2]),
                    "total": row[2],
                    "completion_percentage": min(row[3], 100.0),
                    "last_accessed": row[4]
                }
                for row in cursor.fetchall()
            ]
            
            return {"success": True, "modules": modules}
    except Exception as e:
        print(f"Error fetching module progress: {e}")
        return {"success": False, "error": str(e)}


def get_attempt_history(username, scenario_type=None, limit=20):
    """
    Get detailed history of scenario attempts for a user.
    """
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            
            if scenario_type:
                cursor.execute("""
                    SELECT id, scenario_type, scenario_platform, user_choice, correct_answer,
                           is_correct, difficulty_level, duration_seconds, start_time
                    FROM scenario_attempts
                    WHERE username = ? AND scenario_type = ?
                    ORDER BY start_time DESC
                    LIMIT ?
                """, (username, scenario_type, limit))
            else:
                cursor.execute("""
                    SELECT id, scenario_type, scenario_platform, user_choice, correct_answer,
                           is_correct, difficulty_level, duration_seconds, start_time
                    FROM scenario_attempts
                    WHERE username = ?
                    ORDER BY start_time DESC
                    LIMIT ?
                """, (username, limit))
            
            attempts = [
                {
                    "id": row[0],
                    "scenario_type": row[1],
                    "platform": row[2],
                    "user_choice": row[3],
                    "correct_answer": row[4],
                    "correct": row[5],
                    "difficulty": row[6],
                    "duration_seconds": row[7],
                    "timestamp": row[8]
                }
                for row in cursor.fetchall()
            ]
            
            return {"success": True, "attempts": attempts}
    except Exception as e:
        print(f"Error fetching attempt history: {e}")
        return {"success": False, "error": str(e)}


def get_survey_comparison(username):
    """
    Compare pre-survey and post-survey results for behavioral change assessment.
    """
    try:
        with _connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT module_name,
                       ROUND(AVG(CASE WHEN phase = 'pre' THEN CASE WHEN is_correct THEN 1 ELSE 0 END END) * 100.0, 1) AS pre_score,
                       ROUND(AVG(CASE WHEN phase = 'post' THEN CASE WHEN is_correct THEN 1 ELSE 0 END END) * 100.0, 1) AS post_score,
                       SUM(CASE WHEN phase = 'pre' THEN 1 ELSE 0 END) AS pre_count,
                       SUM(CASE WHEN phase = 'post' THEN 1 ELSE 0 END) AS post_count
                FROM module_assessment_results
                WHERE username = ?
                GROUP BY module_name
                ORDER BY module_name
            """, (username,))
            module_rows = cursor.fetchall()

            module_assessments = []
            for row in module_rows:
                pre_score = row[1]
                post_score = row[2]
                score_change = None
                if pre_score is not None and post_score is not None:
                    score_change = round(post_score - pre_score, 1)

                module_assessments.append({
                    "module_name": row[0],
                    "pre_score": pre_score,
                    "post_score": post_score,
                    "pre_count": row[3],
                    "post_count": row[4],
                    "score_change": score_change,
                })
            
            # Get pre-survey
            cursor.execute("""
                SELECT age, device, confidence
                FROM pre_survey
                WHERE username = ?
            """, (username,))
            pre_row = cursor.fetchone()
            
            # Get post-survey
            cursor.execute("""
                SELECT confidence_rating, perceived_usefulness, behavior_change,
                       recommendation_likelihood, learning_rating, completed_timestamp
                FROM post_survey
                WHERE username = ?
                ORDER BY completed_timestamp DESC
                LIMIT 1
            """, (username,))
            post_row = cursor.fetchone()
            
            pre_survey = None
            if pre_row:
                pre_survey = {
                    "age": pre_row[0],
                    "device": pre_row[1],
                    "confidence": pre_row[2]
                }
            
            post_survey = None
            if post_row:
                post_survey = {
                    "confidence": post_row[0],
                    "perceived_usefulness": post_row[1],
                    "behavior_change": post_row[2],
                    "recommendation_likelihood": post_row[3],
                    "learning_rating": post_row[4],
                    "completed": post_row[5]
                }
            
            confidence_change = None
            if pre_survey and post_survey:
                confidence_change = post_survey["confidence"] - pre_survey["confidence"]
            
            return {
                "success": True,
                "pre_survey": pre_survey,
                "post_survey": post_survey,
                "confidence_change": confidence_change,
                "module_assessments": module_assessments,
            }
    except Exception as e:
        print(f"Error fetching survey comparison: {e}")
        return {"success": False, "error": str(e)}


def get_learning_metrics(username):
    """
    Comprehensive learning metrics including time spent, difficulty progression,
    and identified critical indicators.
    """
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            
            # Total time spent
            cursor.execute("""
                SELECT SUM(duration_seconds)
                FROM scenario_attempts
                WHERE username = ?
            """, (username,))
            total_time = cursor.fetchone()[0] or 0
            
            # Total attempts and correct
            cursor.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)
                FROM scenario_attempts
                WHERE username = ?
            """, (username,))
            row = cursor.fetchone()
            total_attempts = row[0]
            correct_attempts = row[1] or 0
            
            # Difficulty progression (current difficulty for each scenario)
            cursor.execute("""
                SELECT 'email_desktop' as type, difficulty_email_desktop as level
                FROM users WHERE username = ?
                UNION ALL
                SELECT 'internet_desktop', difficulty_internet_desktop FROM users WHERE username = ?
                UNION ALL
                SELECT 'email_mobile', difficulty_email_mobile FROM users WHERE username = ?
                UNION ALL
                SELECT 'sms_mobile', difficulty_sms_mobile FROM users WHERE username = ?
                UNION ALL
                SELECT 'call_mobile', difficulty_call_mobile FROM users WHERE username = ?
                UNION ALL
                SELECT 'web_mobile', difficulty_web_mobile FROM users WHERE username = ?
            """, (username, username, username, username, username, username))
            difficulty_rows = cursor.fetchall()

            cursor.execute("""
                SELECT COUNT(*)
                FROM critical_indicators
                WHERE username = ?
            """, (username,))
            total_indicators = cursor.fetchone()[0] or 0
            
            difficulty_progression = [
                {"scenario": row[0], "current_difficulty": row[1]}
                for row in difficulty_rows
            ]
            
            overall_success_rate = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
            
            return {
                "success": True,
                "metrics": {
                    "total_time_spent_seconds": int(total_time),
                    "total_attempts": total_attempts,
                    "correct_attempts": correct_attempts,
                    "total_indicators_identified": total_indicators,
                    "overall_success_rate": round(overall_success_rate, 2),
                    "difficulty_progression": difficulty_progression
                }
            }
    except Exception as e:
        print(f"Error fetching learning metrics: {e}")
        return {"success": False, "error": str(e)}
