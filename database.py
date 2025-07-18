import streamlit as st
import snowflake.connector
import json
import pandas as pd
from datetime import datetime
from typing import Optional, List, Tuple, Dict
import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# إعدادات اتصال Snowflake
SNOWFLAKE_ACCOUNT = os.getenv('SNOWFLAKE_ACCOUNT')
SNOWFLAKE_USER = os.getenv('SNOWFLAKE_USER')
SNOWFLAKE_PASSWORD = os.getenv('SNOWFLAKE_PASSWORD')
SNOWFLAKE_DATABASE = os.getenv('SNOWFLAKE_DATABASE', 'SURVEY_APP')
SNOWFLAKE_SCHEMA = os.getenv('SNOWFLAKE_SCHEMA', 'PUBLIC')
SNOWFLAKE_WAREHOUSE = os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')

def get_snowflake_connection():
    """إنشاء اتصال بـ Snowflake"""
    try:
        conn = snowflake.connector.connect(
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            account=SNOWFLAKE_ACCOUNT,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA
        )
        return conn
    except Exception as e:
        st.error(f"فشل الاتصال بـ Snowflake: {str(e)}")
        return None

def init_db():
    """تهيئة قاعدة البيانات وجداولها"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # إنشاء الجداول إذا لم تكن موجودة
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER AUTOINCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL,
            assigned_region INTEGER,
            created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            last_login TIMESTAMP_NTZ,
            last_activity TIMESTAMP_NTZ
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Governorates (
            governorate_id INTEGER AUTOINCREMENT PRIMARY KEY,
            governorate_name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS HealthAdministrations (
            admin_id INTEGER AUTOINCREMENT PRIMARY KEY,
            admin_name VARCHAR(255) NOT NULL,
            description TEXT,
            governorate_id INTEGER NOT NULL,
            FOREIGN KEY (governorate_id) REFERENCES Governorates(governorate_id),
            UNIQUE (admin_name, governorate_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Surveys (
            survey_id INTEGER AUTOINCREMENT PRIMARY KEY,
            survey_name VARCHAR(255) NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (created_by) REFERENCES Users(user_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Survey_Fields (
            field_id INTEGER AUTOINCREMENT PRIMARY KEY,
            survey_id INTEGER NOT NULL,
            field_type VARCHAR(50) NOT NULL,
            field_label VARCHAR(255) NOT NULL,
            field_options TEXT,
            is_required BOOLEAN DEFAULT FALSE,
            field_order INTEGER NOT NULL,
            FOREIGN KEY (survey_id) REFERENCES Surveys(survey_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Responses (
            response_id INTEGER AUTOINCREMENT PRIMARY KEY,
            survey_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            region_id INTEGER NOT NULL,
            submission_date TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            is_completed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (survey_id) REFERENCES Surveys(survey_id),
            FOREIGN KEY (user_id) REFERENCES Users(user_id),
            FOREIGN KEY (region_id) REFERENCES HealthAdministrations(admin_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Response_Details (
            detail_id INTEGER AUTOINCREMENT PRIMARY KEY,
            response_id INTEGER NOT NULL,
            field_id INTEGER NOT NULL,
            answer_value TEXT,
            FOREIGN KEY (response_id) REFERENCES Responses(response_id),
            FOREIGN KEY (field_id) REFERENCES Survey_Fields(field_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS GovernorateAdmins (
            admin_id INTEGER AUTOINCREMENT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            governorate_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(user_id),
            FOREIGN KEY (governorate_id) REFERENCES Governorates(governorate_id),
            UNIQUE (user_id, governorate_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS UserSurveys (
            id INTEGER AUTOINCREMENT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            survey_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(user_id),
            FOREIGN KEY (survey_id) REFERENCES Surveys(survey_id),
            UNIQUE (user_id, survey_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS SurveyGovernorate (
            id INTEGER AUTOINCREMENT PRIMARY KEY,
            survey_id INTEGER NOT NULL,
            governorate_id INTEGER NOT NULL,
            FOREIGN KEY (survey_id) REFERENCES Surveys(survey_id),
            FOREIGN KEY (governorate_id) REFERENCES Governorates(governorate_id),
            UNIQUE (survey_id, governorate_id)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS AuditLog (
            log_id INTEGER AUTOINCREMENT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            table_name VARCHAR(255) NOT NULL,
            record_id INTEGER,
            old_value TEXT,
            new_value TEXT,
            action_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        )
        """)
        
        # إضافة مستخدم admin افتراضي إذا لم يكن موجوداً
        cursor.execute("SELECT COUNT(*) FROM Users WHERE role='admin'")
        if cursor.fetchone()[0] == 0:
            from auth import hash_password
            admin_password = hash_password("admin123")
            cursor.execute("""
            INSERT INTO Users (username, password_hash, role)
            VALUES (%s, %s, 'admin')
            """, ("admin", admin_password))
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"حدث خطأ في تهيئة قاعدة البيانات: {str(e)}")
        return False
    finally:
        conn.close()

# دوال المستخدمين
def get_user_by_username(username):
    """الحصول على مستخدم بواسطة اسم المستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE username=%s", (username,))
        return cursor.fetchone()
    except Exception as e:
        st.error(f"حدث خطأ في جلب بيانات المستخدم: {str(e)}")
        return None
    finally:
        conn.close()

def get_user_role(user_id):
    """الحصول على دور المستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM Users WHERE user_id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        st.error(f"حدث خطأ في جلب دور المستخدم: {str(e)}")
        return None
    finally:
        conn.close()

def update_last_login(user_id):
    """تحديث وقت آخر دخول للمستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE Users 
        SET last_login = CURRENT_TIMESTAMP() 
        WHERE user_id = %s
        """, (user_id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث آخر دخول: {str(e)}")
        return False
    finally:
        conn.close()

def update_user_activity(user_id):
    """تحديث وقت آخر نشاط للمستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE Users 
        SET last_activity = CURRENT_TIMESTAMP() 
        WHERE user_id = %s
        """, (user_id,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث آخر نشاط: {str(e)}")
        return False
    finally:
        conn.close()

def add_user(username, password, role, region_id=None):
    """إضافة مستخدم جديد"""
    from auth import hash_password
    
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # التحقق من عدم وجود مستخدم بنفس الاسم
        cursor.execute("SELECT 1 FROM Users WHERE username=%s", (username,))
        if cursor.fetchone():
            st.error("اسم المستخدم موجود بالفعل!")
            return False
        
        # إضافة المستخدم
        cursor.execute("""
        INSERT INTO Users (username, password_hash, role, assigned_region)
        VALUES (%s, %s, %s, %s)
        """, (username, hash_password(password), role, region_id))
        
        conn.commit()
        st.success("تمت إضافة المستخدم بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في إضافة المستخدم: {str(e)}")
        return False
    finally:
        conn.close()

def update_user(user_id, username, role, region_id=None):
    """تحديث بيانات المستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # الحصول على القيم القديمة أولاً
        cursor.execute("""
        SELECT username, role, assigned_region 
        FROM Users 
        WHERE user_id=%s
        """, (user_id,))
        old_data = cursor.fetchone()
        
        # التحقق من عدم وجود مستخدم آخر بنفس الاسم
        cursor.execute("""
        SELECT 1 FROM Users 
        WHERE username=%s AND user_id!=%s
        """, (username, user_id))
        if cursor.fetchone():
            st.error("اسم المستخدم موجود بالفعل!")
            return False
        
        # تحديث بيانات المستخدم
        cursor.execute("""
        UPDATE Users 
        SET username=%s, role=%s, assigned_region=%s 
        WHERE user_id=%s
        """, (username, role, region_id, user_id))
        
        if role == 'governorate_admin':
            # حذف أي تعيينات سابقة لمسؤول المحافظة
            cursor.execute("""
            DELETE FROM GovernorateAdmins 
            WHERE user_id=%s
            """, (user_id,))
        
        conn.commit()
        
        # تسجيل التعديل في سجل التعديلات
        new_data = (username, role, region_id)
        changes = {
            'username': {'old': old_data[0], 'new': new_data[0]},
            'role': {'old': old_data[1], 'new': new_data[1]},
            'assigned_region': {'old': old_data[2], 'new': new_data[2]}
        }
        log_audit_action(
            st.session_state.user_id, 
            'UPDATE', 
            'Users', 
            user_id,
            old_data,
            new_data
        )
        
        st.success("تم تحديث بيانات المستخدم بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث المستخدم: {str(e)}")
        return False
    finally:
        conn.close()

def delete_user(user_id):
    """حذف مستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # التحقق من وجود إجابات مرتبطة بالمستخدم
        cursor.execute("SELECT 1 FROM Responses WHERE user_id=%s", (user_id,))
        if cursor.fetchone():
            st.error("لا يمكن حذف المستخدم لأنه لديه إجابات مسجلة!")
            return False
        
        # حذف المستخدم
        cursor.execute("DELETE FROM Users WHERE user_id=%s", (user_id,))
        conn.commit()
        st.success("تم حذف المستخدم بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء حذف المستخدم: {str(e)}")
        return False
    finally:
        conn.close()

# دوال المحافظات والإدارات الصحية
def get_governorates_list():
    """الحصول على قائمة المحافظات"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT governorate_id, governorate_name 
        FROM Governorates
        ORDER BY governorate_name
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب قائمة المحافظات: {str(e)}")
        return []
    finally:
        conn.close()

def get_health_admins():
    """الحصول على قائمة الإدارات الصحية"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT admin_id, admin_name 
        FROM HealthAdministrations
        ORDER BY admin_name
        """)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب قائمة الإدارات الصحية: {str(e)}")
        return []
    finally:
        conn.close()

def get_health_admin_name(admin_id):
    """الحصول على اسم الإدارة الصحية"""
    if admin_id is None:
        return "غير معين"
    
    conn = get_snowflake_connection()
    if not conn:
        return "خطأ في النظام"
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT admin_name 
        FROM HealthAdministrations 
        WHERE admin_id=%s
        """, (admin_id,))
        result = cursor.fetchone()
        return result[0] if result else "غير معروف"
    except Exception as e:
        st.error(f"حدث خطأ في جلب اسم الإدارة الصحية: {str(e)}")
        return "خطأ في النظام"
    finally:
        conn.close()

def add_health_admin(admin_name, description, governorate_id):
    """إضافة إدارة صحية جديدة"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # التحقق من عدم وجود إدارة بنفس الاسم في نفس المحافظة
        cursor.execute("""
        SELECT 1 FROM HealthAdministrations 
        WHERE admin_name=%s AND governorate_id=%s
        """, (admin_name, governorate_id))
        if cursor.fetchone():
            st.error("هذه الإدارة الصحية موجودة بالفعل في هذه المحافظة!")
            return False
        
        # إضافة الإدارة الجديدة
        cursor.execute("""
        INSERT INTO HealthAdministrations (admin_name, description, governorate_id)
        VALUES (%s, %s, %s)
        """, (admin_name, description, governorate_id))
        
        conn.commit()
        st.success(f"تمت إضافة الإدارة الصحية '{admin_name}' بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في إضافة الإدارة الصحية: {str(e)}")
        return False
    finally:
        conn.close()

def update_health_admin(admin_id, admin_name, description, governorate_id):
    """تحديث بيانات الإدارة الصحية"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # التحقق من عدم وجود إدارة أخرى بنفس الاسم في نفس المحافظة
        cursor.execute("""
        SELECT 1 FROM HealthAdministrations 
        WHERE admin_name=%s AND governorate_id=%s AND admin_id!=%s
        """, (admin_name, governorate_id, admin_id))
        if cursor.fetchone():
            st.error("هذا الاسم مستخدم بالفعل لإدارة أخرى في هذه المحافظة!")
            return False
        
        # تحديث بيانات الإدارة
        cursor.execute("""
        UPDATE HealthAdministrations 
        SET admin_name=%s, description=%s, governorate_id=%s 
        WHERE admin_id=%s
        """, (admin_name, description, governorate_id, admin_id))
        
        conn.commit()
        st.success("تم تحديث الإدارة الصحية بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث الإدارة الصحية: {str(e)}")
        return False
    finally:
        conn.close()

def delete_health_admin(admin_id):
    """حذف إدارة صحية"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # التحقق من عدم وجود مستخدمين مرتبطين بالإدارة
        cursor.execute("SELECT 1 FROM Users WHERE assigned_region=%s", (admin_id,))
        if cursor.fetchone():
            st.error("لا يمكن حذف الإدارة الصحية لأنها مرتبطة بمستخدمين!")
            return False
        
        # حذف الإدارة
        cursor.execute("DELETE FROM HealthAdministrations WHERE admin_id=%s", (admin_id,))
        conn.commit()
        st.success("تم حذف الإدارة الصحية بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء حذف الإدارة الصحية: {str(e)}")
        return False
    finally:
        conn.close()

# دوال مسؤولي المحافظات
def get_governorate_admin(user_id):
    """الحصول على محافظات مسؤول المحافظة"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT g.governorate_id, g.governorate_name 
        FROM GovernorateAdmins ga
        JOIN Governorates g ON ga.governorate_id = g.governorate_id
        WHERE ga.user_id = %s
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب محافظات المسؤول: {str(e)}")
        return []
    finally:
        conn.close()

def get_governorate_admin_data(user_id):
    """الحصول على بيانات مسؤول المحافظة"""
    conn = get_snowflake_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT g.governorate_id, g.governorate_name, g.description 
        FROM GovernorateAdmins ga
        JOIN Governorates g ON ga.governorate_id = g.governorate_id
        WHERE ga.user_id = %s
        """, (user_id,))
        return cursor.fetchone()
    except Exception as e:
        st.error(f"حدث خطأ في جلب بيانات المحافظة: {str(e)}")
        return None
    finally:
        conn.close()

def add_governorate_admin(user_id, governorate_id):
    """إضافة مسؤول محافظة"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO GovernorateAdmins (user_id, governorate_id)
        VALUES (%s, %s)
        """, (user_id, governorate_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في إضافة مسؤول المحافظة: {str(e)}")
        return False
    finally:
        conn.close()

# دوال الاستبيانات
def save_survey(survey_name, fields, governorate_ids=None):
    """حفظ استبيان جديد"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # 1. حفظ الاستبيان الأساسي
        cursor.execute("""
        INSERT INTO Surveys (survey_name, created_by)
        VALUES (%s, %s)
        """, (survey_name, st.session_state.user_id))
        
        # الحصول على معرف الاستبيان الجديد
        cursor.execute("SELECT LAST_INSERT_ID()")
        survey_id = cursor.fetchone()[0]
        
        # 2. ربط الاستبيان بالمحافظات
        if governorate_ids:
            for gov_id in governorate_ids:
                cursor.execute("""
                INSERT INTO SurveyGovernorate (survey_id, governorate_id)
                VALUES (%s, %s)
                """, (survey_id, gov_id))
        
        # 3. حفظ حقول الاستبيان
        for i, field in enumerate(fields):
            field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
            
            cursor.execute("""
            INSERT INTO Survey_Fields (
                survey_id, field_type, field_label, 
                field_options, is_required, field_order
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                survey_id, 
                field['field_type'], 
                field['field_label'],
                field_options,
                field.get('is_required', False),
                i + 1
            ))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في حفظ الاستبيان: {str(e)}")
        return False
    finally:
        conn.close()

def get_governorate_surveys(governorate_id):
    """الحصول على استبيانات المحافظة"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT s.survey_id, s.survey_name, s.created_at, s.is_active
        FROM Surveys s
        JOIN SurveyGovernorate sg ON s.survey_id = sg.survey_id
        WHERE sg.governorate_id = %s
        ORDER BY s.created_at DESC
        """, (governorate_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب استبيانات المحافظة: {str(e)}")
        return []
    finally:
        conn.close()

def get_survey_fields(survey_id):
    """الحصول على حقول الاستبيان"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            field_id, 
            field_label, 
            field_type, 
            field_options, 
            is_required, 
            field_order
        FROM Survey_Fields
        WHERE survey_id = %s
        ORDER BY field_order
        """, (survey_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب حقول الاستبيان: {str(e)}")
        return []
    finally:
        conn.close()

def update_survey(survey_id, survey_name, is_active, fields):
    """تحديث بيانات الاستبيان"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # 1. تحديث بيانات الاستبيان الأساسية
        cursor.execute("""
        UPDATE Surveys 
        SET survey_name=%s, is_active=%s 
        WHERE survey_id=%s
        """, (survey_name, is_active, survey_id))
        
        # 2. تحديث الحقول الموجودة أو إضافة جديدة
        for field in fields:
            field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
            
            if 'field_id' in field:  # حقل موجود يتم تحديثه
                cursor.execute("""
                UPDATE Survey_Fields 
                SET field_label=%s, field_type=%s, field_options=%s, is_required=%s
                WHERE field_id=%s
                """, (
                    field['field_label'], 
                    field['field_type'],
                    field_options,
                    field.get('is_required', False),
                    field['field_id']
                ))
            else:  # حقل جديد يتم إضافته
                cursor.execute("""
                SELECT MAX(field_order) 
                FROM Survey_Fields 
                WHERE survey_id=%s
                """, (survey_id,))
                max_order = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                INSERT INTO Survey_Fields (
                    survey_id, field_label, field_type, 
                    field_options, is_required, field_order
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    survey_id,
                    field['field_label'],
                    field['field_type'],
                    field_options,
                    field.get('is_required', False),
                    max_order + 1
                ))
        
        conn.commit()
        st.success("تم تحديث الاستبيان بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث الاستبيان: {str(e)}")
        return False
    finally:
        conn.close()

def delete_survey(survey_id):
    """حذف استبيان"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # حذف تفاصيل الإجابات المرتبطة
        cursor.execute("""
        DELETE FROM Response_Details 
        WHERE response_id IN (
            SELECT response_id FROM Responses WHERE survey_id = %s
        )
        """, (survey_id,))
        
        # حذف الإجابات المرتبطة
        cursor.execute("""
        DELETE FROM Responses 
        WHERE survey_id = %s
        """, (survey_id,))
        
        # حذف حقول الاستبيان
        cursor.execute("""
        DELETE FROM Survey_Fields 
        WHERE survey_id = %s
        """, (survey_id,))
        
        # حذف الاستبيان نفسه
        cursor.execute("""
        DELETE FROM Surveys 
        WHERE survey_id = %s
        """, (survey_id,))
        
        conn.commit()
        st.success("تم حذف الاستبيان بنجاح")
        return True
    except Exception as e:
        st.error(f"حدث خطأ أثناء حذف الاستبيان: {str(e)}")
        return False
    finally:
        conn.close()

# دوال الإجابات
def save_response(survey_id, user_id, region_id, is_completed=False):
    """حفظ إجابة جديدة"""
    conn = get_snowflake_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO Responses (survey_id, user_id, region_id, is_completed)
        VALUES (%s, %s, %s, %s)
        """, (survey_id, user_id, region_id, is_completed))
        
        # الحصول على معرف الإجابة الجديدة
        cursor.execute("SELECT LAST_INSERT_ID()")
        response_id = cursor.fetchone()[0]
        
        conn.commit()
        return response_id
    except Exception as e:
        st.error(f"حدث خطأ في حفظ الإجابة: {str(e)}")
        return None
    finally:
        conn.close()

def save_response_detail(response_id, field_id, answer_value):
    """حفظ تفاصيل الإجابة"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO Response_Details (response_id, field_id, answer_value)
        VALUES (%s, %s, %s)
        """, (response_id, field_id, str(answer_value) if answer_value is not None else ""))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في حفظ تفاصيل الإجابة: {str(e)}")
        return False
    finally:
        conn.close()

def get_response_info(response_id):
    """الحصول على معلومات أساسية عن الإجابة"""
    conn = get_snowflake_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            r.response_id, s.survey_name, u.username, 
            ha.admin_name, g.governorate_name, r.submission_date
        FROM Responses r
        JOIN Surveys s ON r.survey_id = s.survey_id
        JOIN Users u ON r.user_id = u.user_id
        JOIN HealthAdministrations ha ON r.region_id = ha.admin_id
        JOIN Governorates g ON ha.governorate_id = g.governorate_id
        WHERE r.response_id = %s
        """, (response_id,))
        return cursor.fetchone()
    except Exception as e:
        st.error(f"حدث خطأ في جلب معلومات الإجابة: {str(e)}")
        return None
    finally:
        conn.close()

def get_response_details(response_id):
    """الحصول على تفاصيل الإجابة"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            rd.detail_id, rd.field_id, sf.field_label, 
            sf.field_type, sf.field_options, rd.answer_value
        FROM Response_Details rd
        JOIN Survey_Fields sf ON rd.field_id = sf.field_id
        WHERE rd.response_id = %s
        ORDER BY sf.field_order
        """, (response_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب تفاصيل الإجابة: {str(e)}")
        return []
    finally:
        conn.close()

def update_response_detail(detail_id, new_value):
    """تحديث تفاصيل الإجابة"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE Response_Details 
        SET answer_value = %s 
        WHERE detail_id = %s
        """, (new_value, detail_id))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث الإجابة: {str(e)}")
        return False
    finally:
        conn.close()

def has_completed_survey_today(user_id, survey_id):
    """التحقق من إكمال الاستبيان اليوم"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 1 FROM Responses 
        WHERE user_id = %s AND survey_id = %s AND is_completed = TRUE
        AND DATE(submission_date) = CURRENT_DATE()
        LIMIT 1
        """, (user_id, survey_id))
        return cursor.fetchone() is not None
    except Exception as e:
        st.error(f"حدث خطأ في التحقق من إكمال الاستبيان: {str(e)}")
        return False
    finally:
        conn.close()

# دوال الموظفين
def get_governorate_employees(governorate_id):
    """الحصول على موظفي المحافظة"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT u.user_id, u.username, ha.admin_name
        FROM Users u
        JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
        WHERE ha.governorate_id = %s AND u.role = 'employee'
        ORDER BY u.username
        """, (governorate_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب موظفي المحافظة: {str(e)}")
        return []
    finally:
        conn.close()

def get_user_allowed_surveys(user_id):
    """الحصول على الاستبيانات المسموح بها للمستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT s.survey_id, s.survey_name 
        FROM Surveys s
        JOIN UserSurveys us ON s.survey_id = us.survey_id
        WHERE us.user_id = %s
        ORDER BY s.survey_name
        """, (user_id,))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب الاستبيانات المسموح بها: {str(e)}")
        return []
    finally:
        conn.close()

def update_user_allowed_surveys(user_id, survey_ids):
    """تحديث الاستبيانات المسموح بها للمستخدم"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # الحصول على محافظة المستخدم
        cursor.execute("""
        SELECT ha.governorate_id 
        FROM Users u
        JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
        WHERE u.user_id = %s
        """, (user_id,))
        governorate_id = cursor.fetchone()
        
        if not governorate_id:
            st.error("المستخدم غير مرتبط بمحافظة")
            return False
        
        # التحقق من أن الاستبيانات مسموحة للمحافظة
        valid_surveys = []
        for survey_id in survey_ids:
            cursor.execute("""
            SELECT 1 FROM SurveyGovernorate 
            WHERE survey_id = %s AND governorate_id = %s
            """, (survey_id, governorate_id[0]))
            if cursor.fetchone():
                valid_surveys.append(survey_id)
        
        # حذف جميع التصاريح الحالية
        cursor.execute("DELETE FROM UserSurveys WHERE user_id=%s", (user_id,))
        
        # إضافة التصاريح الجديدة
        for survey_id in valid_surveys:
            cursor.execute("""
            INSERT INTO UserSurveys (user_id, survey_id)
            VALUES (%s, %s)
            """, (user_id, survey_id))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تحديث الاستبيانات المسموح بها: {str(e)}")
        return False
    finally:
        conn.close()

# دوال سجل التعديلات
def log_audit_action(user_id, action_type, table_name, record_id=None, old_value=None, new_value=None):
    """تسجيل إجراء في سجل التعديلات"""
    conn = get_snowflake_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO AuditLog (
            user_id, action_type, table_name, 
            record_id, old_value, new_value
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user_id, 
            action_type, 
            table_name, 
            record_id,
            json.dumps(old_value) if old_value else None,
            json.dumps(new_value) if new_value else None
        ))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"حدث خطأ في تسجيل الإجراء: {str(e)}")
        return False
    finally:
        conn.close()

def get_audit_logs(table_name=None, action_type=None, username=None, date_range=None, search_query=None):
    """الحصول على سجل التعديلات مع فلاتر متقدمة"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            a.log_id, u.username, a.action_type, a.table_name, 
            a.record_id, a.old_value, a.new_value, a.action_timestamp
        FROM AuditLog a
        JOIN Users u ON a.user_id = u.user_id
        """
        params = []
        conditions = []
        
        # تطبيق الفلاتر
        if table_name:
            conditions.append("a.table_name = %s")
            params.append(table_name)
        if action_type:
            conditions.append("a.action_type = %s")
            params.append(action_type)
        if username:
            conditions.append("u.username LIKE %s")
            params.append(f"%{username}%")
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            conditions.append("DATE(a.action_timestamp) BETWEEN %s AND %s")
            params.extend([start_date, end_date])
        if search_query:
            conditions.append("""
            (a.old_value LIKE %s OR 
             a.new_value LIKE %s OR 
             u.username LIKE %s OR 
             a.table_name LIKE %s OR
             a.action_type LIKE %s)
            """)
            search_term = f"%{search_query}%"
            params.extend([search_term, search_term, search_term, search_term, search_term])
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
            
        query += ' ORDER BY a.action_timestamp DESC'
        
        cursor.execute(query, params)
        return cursor.fetchall()
    except Exception as e:
        st.error(f"حدث خطأ في جلب سجل التعديلات: {str(e)}")
        return []
    finally:
        conn.close()
