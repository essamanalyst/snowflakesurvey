import os
import json
from snowflake.snowpark import Session
from snowflake.snowpark.exceptions import SnowparkSQLException
import streamlit as st
from typing import Optional, List, Tuple, Dict
from datetime import datetime

# تكوين اتصال Snowflake
def get_snowflake_session():
    connection_params = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
        "role": os.getenv("SNOWFLAKE_ROLE")
    }
    return Session.builder.configs(connection_params).create()

# تهيئة الجداول
def init_db():
    try:
        session = get_snowflake_session()
        
        # إنشاء جدول المستخدمين
        session.sql('''
        CREATE TABLE IF NOT EXISTS USERS (
            USER_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            USERNAME VARCHAR(255) UNIQUE NOT NULL,
            PASSWORD_HASH VARCHAR(255) NOT NULL,
            ROLE VARCHAR(50) NOT NULL,
            ASSIGNED_REGION INTEGER,
            CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            LAST_LOGIN TIMESTAMP_NTZ,
            LAST_ACTIVITY TIMESTAMP_NTZ
        )
        ''').collect()
        
        # إنشاء جدول المحافظات
        session.sql('''
        CREATE TABLE IF NOT EXISTS GOVERNORATES (
            GOVERNORATE_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            GOVERNORATE_NAME VARCHAR(255) NOT NULL UNIQUE,
            DESCRIPTION VARCHAR(1000)
        )
        ''').collect()
        
        # إنشاء جدول الإدارات الصحية
        session.sql('''
        CREATE TABLE IF NOT EXISTS HEALTH_ADMINISTRATIONS (
            ADMIN_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            ADMIN_NAME VARCHAR(255) NOT NULL,
            DESCRIPTION VARCHAR(1000),
            GOVERNORATE_ID INTEGER NOT NULL,
            CONSTRAINT FK_GOVERNORATE FOREIGN KEY (GOVERNORATE_ID) REFERENCES GOVERNORATES(GOVERNORATE_ID),
            CONSTRAINT UNIQUE_ADMIN UNIQUE (ADMIN_NAME, GOVERNORATE_ID)
        )
        ''').collect()
        
        # إنشاء جدول الاستبيانات
        session.sql('''
        CREATE TABLE IF NOT EXISTS SURVEYS (
            SURVEY_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            SURVEY_NAME VARCHAR(255) NOT NULL,
            CREATED_BY INTEGER NOT NULL,
            CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            IS_ACTIVE BOOLEAN DEFAULT TRUE,
            CONSTRAINT FK_CREATOR FOREIGN KEY (CREATED_BY) REFERENCES USERS(USER_ID)
        )
        ''').collect()
        
        # إنشاء جدول حقول الاستبيان
        session.sql('''
        CREATE TABLE IF NOT EXISTS SURVEY_FIELDS (
            FIELD_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            SURVEY_ID INTEGER NOT NULL,
            FIELD_TYPE VARCHAR(50) NOT NULL,
            FIELD_LABEL VARCHAR(255) NOT NULL,
            FIELD_OPTIONS VARCHAR(2000),
            IS_REQUIRED BOOLEAN DEFAULT FALSE,
            FIELD_ORDER INTEGER NOT NULL,
            CONSTRAINT FK_SURVEY FOREIGN KEY (SURVEY_ID) REFERENCES SURVEYS(SURVEY_ID)
        )
        ''').collect()
        
        # إنشاء جدول الإجابات
        session.sql('''
        CREATE TABLE IF NOT EXISTS RESPONSES (
            RESPONSE_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            SURVEY_ID INTEGER NOT NULL,
            USER_ID INTEGER NOT NULL,
            REGION_ID INTEGER NOT NULL,
            SUBMISSION_DATE TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            IS_COMPLETED BOOLEAN DEFAULT FALSE,
            CONSTRAINT FK_SURVEY_RESPONSE FOREIGN KEY (SURVEY_ID) REFERENCES SURVEYS(SURVEY_ID),
            CONSTRAINT FK_USER_RESPONSE FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID),
            CONSTRAINT FK_REGION_RESPONSE FOREIGN KEY (REGION_ID) REFERENCES HEALTH_ADMINISTRATIONS(ADMIN_ID)
        )
        ''').collect()
        
        # إنشاء جدول تفاصيل الإجابات
        session.sql('''
        CREATE TABLE IF NOT EXISTS RESPONSE_DETAILS (
            DETAIL_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            RESPONSE_ID INTEGER NOT NULL,
            FIELD_ID INTEGER NOT NULL,
            ANSWER_VALUE VARCHAR(2000),
            CONSTRAINT FK_RESPONSE FOREIGN KEY (RESPONSE_ID) REFERENCES RESPONSES(RESPONSE_ID),
            CONSTRAINT FK_FIELD FOREIGN KEY (FIELD_ID) REFERENCES SURVEY_FIELDS(FIELD_ID)
        )
        ''').collect()
        
        # إنشاء جدول مسؤولي المحافظات
        session.sql('''
        CREATE TABLE IF NOT EXISTS GOVERNORATE_ADMINS (
            ADMIN_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            USER_ID INTEGER NOT NULL,
            GOVERNORATE_ID INTEGER NOT NULL,
            CONSTRAINT FK_USER FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID),
            CONSTRAINT FK_GOVERNORATE_ADMIN FOREIGN KEY (GOVERNORATE_ID) REFERENCES GOVERNORATES(GOVERNORATE_ID),
            CONSTRAINT UNIQUE_GOV_ADMIN UNIQUE (USER_ID, GOVERNORATE_ID)
        )
        ''').collect()
        
        # إنشاء جدول الاستبيانات المسموحة للمستخدمين
        session.sql('''
        CREATE TABLE IF NOT EXISTS USER_SURVEYS (
            ID INTEGER AUTOINCREMENT PRIMARY KEY,
            USER_ID INTEGER NOT NULL,
            SURVEY_ID INTEGER NOT NULL,
            CONSTRAINT FK_USER_SURVEY FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID),
            CONSTRAINT FK_SURVEY_PERMISSION FOREIGN KEY (SURVEY_ID) REFERENCES SURVEYS(SURVEY_ID),
            CONSTRAINT UNIQUE_USER_SURVEY UNIQUE (USER_ID, SURVEY_ID)
        )
        ''').collect()
        
        # إنشاء جدول المحافظات المسموحة للاستبيانات
        session.sql('''
        CREATE TABLE IF NOT EXISTS SURVEY_GOVERNORATE (
            ID INTEGER AUTOINCREMENT PRIMARY KEY,
            SURVEY_ID INTEGER NOT NULL,
            GOVERNORATE_ID INTEGER NOT NULL,
            CONSTRAINT FK_SURVEY_GOV FOREIGN KEY (SURVEY_ID) REFERENCES SURVEYS(SURVEY_ID),
            CONSTRAINT FK_GOV_SURVEY FOREIGN KEY (GOVERNORATE_ID) REFERENCES GOVERNORATES(GOVERNORATE_ID),
            CONSTRAINT UNIQUE_SURVEY_GOV UNIQUE (SURVEY_ID, GOVERNORATE_ID)
        )
        ''').collect()
        
        # إنشاء جدول سجل التعديلات
        session.sql('''
        CREATE TABLE IF NOT EXISTS AUDIT_LOG (
            LOG_ID INTEGER AUTOINCREMENT PRIMARY KEY,
            USER_ID INTEGER NOT NULL,
            ACTION_TYPE VARCHAR(50) NOT NULL,
            TABLE_NAME VARCHAR(50) NOT NULL,
            RECORD_ID INTEGER,
            OLD_VALUE VARCHAR(2000),
            NEW_VALUE VARCHAR(2000),
            ACTION_TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            CONSTRAINT FK_USER_AUDIT FOREIGN KEY (USER_ID) REFERENCES USERS(USER_ID)
        )
        ''').collect()
        
        # إضافة مستخدم admin افتراضي إذا لم يكن موجوداً
        admin_count = session.sql("SELECT COUNT(*) FROM USERS WHERE ROLE='admin'").collect()[0][0]
        if admin_count == 0:
            from auth import hash_password
            admin_password = hash_password("admin123")
            session.sql(
                "INSERT INTO USERS (USERNAME, PASSWORD_HASH, ROLE) VALUES (?, ?, ?)",
                params=("admin", admin_password, "admin")
            ).collect()
        
        return True
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في تهيئة قاعدة البيانات: {str(e)}")
        return False
    finally:
        session.close()

# دوال إدارة المستخدمين
def get_user_by_username(username):
    try:
        session = get_snowflake_session()
        user = session.sql("SELECT * FROM USERS WHERE USERNAME=?", params=(username,)).collect()
        
        if user:
            return {
                'user_id': user[0][0],
                'username': user[0][1],
                'password_hash': user[0][2],
                'role': user[0][3],
                'assigned_region': user[0][4],
                'created_at': user[0][5],
                'last_login': user[0][6]
            }
        return None
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب بيانات المستخدم: {str(e)}")
        return None
    finally:
        session.close()

def get_user_role(user_id):
    try:
        session = get_snowflake_session()
        role = session.sql("SELECT ROLE FROM USERS WHERE USER_ID=?", params=(user_id,)).collect()
        return role[0][0] if role else None
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب دور المستخدم: {str(e)}")
        return None
    finally:
        session.close()

# دوال إدارة المحافظات والإدارات الصحية
def get_governorates_list():
    try:
        session = get_snowflake_session()
        governorates = session.sql("SELECT GOVERNORATE_ID, GOVERNORATE_NAME FROM GOVERNORATES").collect()
        return governorates
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب قائمة المحافظات: {str(e)}")
        return []
    finally:
        session.close()

def get_health_admins():
    try:
        session = get_snowflake_session()
        admins = session.sql("SELECT ADMIN_ID, ADMIN_NAME FROM HEALTH_ADMINISTRATIONS").collect()
        return admins
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب الإدارات الصحية: {str(e)}")
        return []
    finally:
        session.close()

def get_health_admin_name(admin_id):
    try:
        session = get_snowflake_session()
        result = session.sql("SELECT ADMIN_NAME FROM HEALTH_ADMINISTRATIONS WHERE ADMIN_ID=?", params=(admin_id,)).collect()
        return result[0][0] if result else "غير معروف"
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب اسم الإدارة الصحية: {str(e)}")
        return "خطأ في النظام"
    finally:
        session.close()

# دوال إدارة الاستبيانات
def save_survey(survey_name, fields, governorate_ids=None):
    try:
        session = get_snowflake_session()
        
        # حفظ الاستبيان الأساسي
        survey_id = session.sql(
            "INSERT INTO SURVEYS (SURVEY_NAME, CREATED_BY) VALUES (?, ?)",
            params=(survey_name, st.session_state.user_id)
        ).collect()[0][0]
        
        # ربط الاستبيان بالمحافظات
        if governorate_ids:
            for gov_id in governorate_ids:
                session.sql(
                    "INSERT INTO SURVEY_GOVERNORATE (SURVEY_ID, GOVERNORATE_ID) VALUES (?, ?)",
                    params=(survey_id, gov_id)
                ).collect()
        
        # حفظ حقول الاستبيان
        for i, field in enumerate(fields):
            field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
            
            session.sql(
                """INSERT INTO SURVEY_FIELDS 
                   (SURVEY_ID, FIELD_TYPE, FIELD_LABEL, FIELD_OPTIONS, IS_REQUIRED, FIELD_ORDER) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                params=(
                    survey_id, 
                    field['field_type'], 
                    field['field_label'],
                    field_options,
                    field.get('is_required', False),
                    i + 1)
            ).collect()
        
        session.commit()
        return True
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في حفظ الاستبيان: {str(e)}")
        return False
    finally:
        session.close()

def get_survey_fields(survey_id):
    try:
        session = get_snowflake_session()
        fields = session.sql('''
            SELECT 
                FIELD_ID, 
                FIELD_LABEL, 
                FIELD_TYPE, 
                FIELD_OPTIONS, 
                IS_REQUIRED, 
                FIELD_ORDER
            FROM SURVEY_FIELDS
            WHERE SURVEY_ID = ?
            ORDER BY FIELD_ORDER
        ''', params=(survey_id,)).collect()
        
        return fields
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب حقول الاستبيان: {str(e)}")
        return []
    finally:
        session.close()

# دوال إدارة الإجابات
def save_response(survey_id, user_id, region_id, is_completed=False):
    try:
        session = get_snowflake_session()
        response_id = session.sql(
            '''INSERT INTO RESPONSES 
               (SURVEY_ID, USER_ID, REGION_ID, IS_COMPLETED) 
               VALUES (?, ?, ?, ?)''',
            params=(survey_id, user_id, region_id, is_completed)
        ).collect()[0][0]
        
        session.commit()
        return response_id
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في حفظ الاستجابة: {str(e)}")
        return None
    finally:
        session.close()

def save_response_detail(response_id, field_id, answer_value):
    try:
        session = get_snowflake_session()
        session.sql(
            "INSERT INTO RESPONSE_DETAILS (RESPONSE_ID, FIELD_ID, ANSWER_VALUE) VALUES (?, ?, ?)",
            params=(response_id, field_id, str(answer_value) if answer_value is not None else "")
        ).collect()
        
        session.commit()
        return True
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في حفظ تفاصيل الإجابة: {str(e)}")
        return False
    finally:
        session.close()

# دوال مسؤولي المحافظات
def get_governorate_admin(user_id):
    try:
        session = get_snowflake_session()
        result = session.sql('''
            SELECT G.GOVERNORATE_ID, G.GOVERNORATE_NAME 
            FROM GOVERNORATE_ADMINS GA
            JOIN GOVERNORATES G ON GA.GOVERNORATE_ID = G.GOVERNORATE_ID
            WHERE GA.USER_ID = ?
        ''', params=(user_id,)).collect()
        
        return result
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب بيانات مسؤول المحافظة: {str(e)}")
        return []
    finally:
        session.close()

def add_governorate_admin(user_id, governorate_id):
    try:
        session = get_snowflake_session()
        session.sql(
            "INSERT INTO GOVERNORATE_ADMINS (USER_ID, GOVERNORATE_ID) VALUES (?, ?)",
            params=(user_id, governorate_id)
        ).collect()
        
        session.commit()
        return True
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في إضافة مسؤول المحافظة: {str(e)}")
        return False
    finally:
        session.close()

# دوال إدارة الصلاحيات
def get_user_allowed_surveys(user_id):
    try:
        session = get_snowflake_session()
        surveys = session.sql('''
            SELECT S.SURVEY_ID, S.SURVEY_NAME 
            FROM SURVEYS S
            JOIN USER_SURVEYS US ON S.SURVEY_ID = US.SURVEY_ID
            WHERE US.USER_ID = ?
            ORDER BY S.SURVEY_NAME
        ''', params=(user_id,)).collect()
        
        return surveys
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب الاستبيانات المسموح بها: {str(e)}")
        return []
    finally:
        session.close()

def update_user_allowed_surveys(user_id, survey_ids):
    try:
        session = get_snowflake_session()
        
        # حذف جميع التصاريح الحالية
        session.sql("DELETE FROM USER_SURVEYS WHERE USER_ID=?", params=(user_id,)).collect()
        
        # إضافة التصاريح الجديدة
        for survey_id in survey_ids:
            session.sql(
                "INSERT INTO USER_SURVEYS (USER_ID, SURVEY_ID) VALUES (?, ?)",
                params=(user_id, survey_id)
            ).collect()
        
        session.commit()
        return True
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في تحديث الاستبيانات المسموح بها: {str(e)}")
        return False
    finally:
        session.close()

# دوال تسجيل النشاط
def update_last_login(user_id):
    try:
        session = get_snowflake_session()
        session.sql(
            "UPDATE USERS SET LAST_LOGIN = CURRENT_TIMESTAMP() WHERE USER_ID = ?", 
            params=(user_id,)
        ).collect()
        
        session.commit()
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في تحديث وقت آخر دخول: {str(e)}")
    finally:
        session.close()

def update_user_activity(user_id):
    try:
        session = get_snowflake_session()
        session.sql(
            "UPDATE USERS SET LAST_ACTIVITY = CURRENT_TIMESTAMP() WHERE USER_ID = ?", 
            params=(user_id,)
        ).collect()
        
        session.commit()
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في تحديث وقت النشاط: {str(e)}")
    finally:
        session.close()

# دوال إضافية
def get_response_details(response_id):
    try:
        session = get_snowflake_session()
        details = session.sql('''
            SELECT RD.DETAIL_ID, RD.FIELD_ID, SF.FIELD_LABEL, 
                   SF.FIELD_TYPE, SF.FIELD_OPTIONS, RD.ANSWER_VALUE
            FROM RESPONSE_DETAILS RD
            JOIN SURVEY_FIELDS SF ON RD.FIELD_ID = SF.FIELD_ID
            WHERE RD.RESPONSE_ID = ?
            ORDER BY SF.FIELD_ORDER
        ''', params=(response_id,)).collect()
        
        return details
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب تفاصيل الإجابة: {str(e)}")
        return []
    finally:
        session.close()

def update_response_detail(detail_id, new_value):
    try:
        session = get_snowflake_session()
        session.sql(
            "UPDATE RESPONSE_DETAILS SET ANSWER_VALUE = ? WHERE DETAIL_ID = ?",
            params=(new_value, detail_id)
        ).collect()
        
        session.commit()
        return True
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في تحديث الإجابة: {str(e)}")
        return False
    finally:
        session.close()

def get_response_info(response_id):
    try:
        session = get_snowflake_session()
        response = session.sql('''
            SELECT R.RESPONSE_ID, S.SURVEY_NAME, U.USERNAME, 
                   HA.ADMIN_NAME, G.GOVERNORATE_NAME, R.SUBMISSION_DATE
            FROM RESPONSES R
            JOIN SURVEYS S ON R.SURVEY_ID = S.SURVEY_ID
            JOIN USERS U ON R.USER_ID = U.USER_ID
            JOIN HEALTH_ADMINISTRATIONS HA ON R.REGION_ID = HA.ADMIN_ID
            JOIN GOVERNORATES G ON HA.GOVERNORATE_ID = G.GOVERNORATE_ID
            WHERE R.RESPONSE_ID = ?
        ''', params=(response_id,)).collect()
        
        return response[0] if response else None
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في جلب معلومات الإجابة: {str(e)}")
        return None
    finally:
        session.close()

def has_completed_survey_today(user_id, survey_id):
    try:
        session = get_snowflake_session()
        result = session.sql('''
            SELECT 1 FROM RESPONSES 
            WHERE USER_ID = ? AND SURVEY_ID = ? AND IS_COMPLETED = TRUE
            AND DATE(SUBMISSION_DATE) = CURRENT_DATE()
            LIMIT 1
        ''', params=(user_id, survey_id)).collect()
        
        return bool(result)
    except SnowparkSQLException as e:
        st.error(f"حدث خطأ في التحقق من إكمال الاستبيان: {str(e)}")
        return False
    finally:
        session.close()
