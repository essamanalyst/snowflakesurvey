import streamlit as st
from database import (
    get_audit_logs, get_response_info, get_response_details, update_response_detail,
    get_user_by_username, update_user_allowed_surveys, add_governorate_admin,
    get_health_admins, update_user, update_survey, get_governorates_list, add_user,
    save_survey, delete_survey, get_all_users, delete_user, get_surveys_list
)
import json
import pandas as pd
from datetime import datetime

def show_admin_dashboard():
    st.title("لوحة تحكم النظام")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "إدارة المستخدمين",
        "إدارة المحافظات", 
        "إدارة الإدارات الصحية",     
        "إدارة الاستبيانات", 
        "عرض البيانات",
    ])
    
    with tab1:
        manage_users()
    
    with tab2:
        manage_governorates()
    
    with tab3:
        manage_regions()
    
    with tab4:
        manage_surveys()
    
    with tab5:
        view_data()
    
def manage_users():
    st.header("إدارة المستخدمين")
    
    # عرض المستخدمين الحاليين
    users = get_all_users()
    
    # عرض جدول المستخدمين
    for user in users:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
        with col1:
            st.write(user['username'])
        with col2:
            role = "مسؤول نظام" if user['role'] == "admin" else "مسؤول محافظة" if user['role'] == "governorate_admin" else "موظف"
            st.write(role)
        with col3:
            st.write(user['governorate_name'] if user['governorate_name'] else "غير محدد")
        with col4:
            st.write(user['admin_name'] if user['admin_name'] else "غير محدد")
        with col5:
            if st.button("تعديل", key=f"edit_{user['user_id']}"):
                st.session_state.editing_user = user['user_id']
        with col6:
            if st.button("حذف", key=f"delete_{user['user_id']}"):
                if delete_user(user['user_id']):
                    st.rerun()
    
    if 'editing_user' in st.session_state:
        edit_user_form(st.session_state.editing_user)
    
    with st.expander("إضافة مستخدم جديد"):
        add_user_form()

def add_user_form():
    governorates = get_governorates_list()
    surveys = get_surveys_list()

    # تهيئة حالة الجلسة
    if 'add_user_form_data' not in st.session_state:
        st.session_state.add_user_form_data = {
            'username': '',
            'password': '',
            'role': 'employee',
            'governorate_id': None,
            'admin_id': None,
            'allowed_surveys': []
        }

    form = st.form(key="add_user_form", clear_on_submit=True)
    
    with form:
        st.subheader("المعلومات الأساسية")
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("اسم المستخدم*", 
                                   value=st.session_state.add_user_form_data['username'],
                                   key="new_user_username")
        with col2:
            password = st.text_input("كلمة المرور*", 
                                   type="password",
                                   value=st.session_state.add_user_form_data['password'],
                                   key="new_user_password")

        role = st.selectbox("الدور*", 
                          ["admin", "governorate_admin", "employee"],
                          index=["admin", "governorate_admin", "employee"].index(
                              st.session_state.add_user_form_data['role']),
                          key="new_user_role")

        # حقول مسؤول المحافظة
        if role == "governorate_admin":
            st.subheader("بيانات مسؤول المحافظة")
            if governorates:
                selected_gov = st.selectbox(
                    "المحافظة*",
                    options=[g[0] for g in governorates],
                    index=[g[0] for g in governorates].index(
                        st.session_state.add_user_form_data['governorate_id']) 
                        if st.session_state.add_user_form_data['governorate_id'] in [g[0] for g in governorates] else 0,
                    format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                    key="gov_admin_select")
                st.session_state.add_user_form_data['governorate_id'] = selected_gov
            else:
                st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")

        # حقول الموظف
        elif role == "employee":
            st.subheader("بيانات الموظف")
            if governorates:
                selected_gov = st.selectbox(
                    "المحافظة*",
                    options=[g[0] for g in governorates],
                    index=[g[0] for g in governorates].index(
                        st.session_state.add_user_form_data['governorate_id']) 
                        if st.session_state.add_user_form_data['governorate_id'] in [g[0] for g in governorates] else 0,
                    format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                    key="employee_gov_select")
                st.session_state.add_user_form_data['governorate_id'] = selected_gov

                # اختيار الإدارة الصحية
                health_admins = get_health_admins(selected_gov)
                
                if health_admins:
                    selected_admin = st.selectbox(
                        "الإدارة الصحية*",
                        options=[a[0] for a in health_admins],
                        index=[a[0] for a in health_admins].index(
                            st.session_state.add_user_form_data['admin_id']) 
                            if st.session_state.add_user_form_data['admin_id'] in [a[0] for a in health_admins] else 0,
                        format_func=lambda x: next(a[1] for a in health_admins if a[0] == x),
                        key="employee_admin_select")
                    st.session_state.add_user_form_data['admin_id'] = selected_admin
                else:
                    st.warning("لا توجد إدارات صحية في هذه المحافظة. يرجى إضافتها أولاً.")
            else:
                st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")

        # قسم الاستبيانات المسموح بها (لغير الأدمن)
        if role != "admin" and surveys:
            st.subheader("الصلاحيات")
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=[s[0] for s in surveys],
                default=st.session_state.add_user_form_data['allowed_surveys'],
                format_func=lambda x: next(s[1] for s in surveys if s[0] == x),
                key="allowed_surveys_select")
            st.session_state.add_user_form_data['allowed_surveys'] = selected_surveys

        # الأزرار الرئيسية
        col1, col2 = st.columns([3, 1])
        with col1:
            submit_button = st.form_submit_button("💾 حفظ المستخدم")
        with col2:
            clear_button = st.form_submit_button("🧹 تنظيف الحقول")

        if submit_button:
            if not username or not password:
                st.error("يرجى إدخال اسم المستخدم وكلمة المرور")
                return

            if role == "governorate_admin" and not st.session_state.add_user_form_data['governorate_id']:
                st.error("يرجى اختيار محافظة لمسؤول المحافظة")
                return

            if role == "employee" and not st.session_state.add_user_form_data['admin_id']:
                st.error("يرجى اختيار إدارة صحية للموظف")
                return

            # حفظ المستخدم في قاعدة البيانات
            if add_user(username, password, role, st.session_state.add_user_form_data['admin_id']):
                user = get_user_by_username(username)
                if user:
                    user_id = user['user_id']

                    # ربط مسؤول المحافظة بالمحافظة
                    if role == "governorate_admin":
                        add_governorate_admin(user_id, st.session_state.add_user_form_data['governorate_id'])

                    # حفظ الاستبيانات المسموح بها
                    if role != "admin" and st.session_state.add_user_form_data['allowed_surveys']:
                        update_user_allowed_surveys(user_id, st.session_state.add_user_form_data['allowed_surveys'])

                    st.success(f"تمت إضافة المستخدم {username} بنجاح")
                    st.session_state.add_user_form_data = {
                        'username': '',
                        'password': '',
                        'role': 'employee',
                        'governorate_id': None,
                        'admin_id': None,
                        'allowed_surveys': []
                    }
                    st.rerun()

        if clear_button:
            st.session_state.add_user_form_data = {
                'username': '',
                'password': '',
                'role': 'employee',
                'governorate_id': None,
                'admin_id': None,
                'allowed_surveys': []
            }
            st.rerun()

def edit_user_form(user_id):
    user = get_user_by_username(user_id)
    if not user:
        st.error("المستخدم غير موجود!")
        del st.session_state.editing_user
        return
    
    governorates = get_governorates_list()
    surveys = get_surveys_list()
    allowed_surveys = get_user_allowed_surveys(user_id)
    allowed_surveys = [s[0] for s in allowed_surveys]
    
    # الحصول على المحافظة الحالية للمستخدم (إذا كان مسؤول محافظة)
    current_gov = None
    current_admin = user['assigned_region']
    if user['role'] == 'governorate_admin':
        gov_info = get_governorate_admin(user_id)
        current_gov = gov_info[0][0] if gov_info else None
    
    with st.form(f"edit_user_{user_id}"):
        new_username = st.text_input("اسم المستخدم", value=user['username'])
        new_role = st.selectbox(
            "الدور", 
            ["admin", "governorate_admin", "employee"],
            index=["admin", "governorate_admin", "employee"].index(user['role'])
        )
        
        if new_role == "governorate_admin":
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                index=[g[0] for g in governorates].index(current_gov) if current_gov else 0,
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key=f"gov_edit_{user_id}"
            )
        elif new_role == "employee":
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                index=[g[0] for g in governorates].index(current_gov) if current_gov else 0,
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key=f"emp_gov_{user_id}"
            )
            
            health_admins = get_health_admins(selected_gov)
            
            admin_options = [a[0] for a in health_admins]
            try:
                admin_index = admin_options.index(current_admin) if current_admin else 0
            except ValueError:
                admin_index = 0
            
            selected_admin = st.selectbox(
                "الإدارة الصحية",
                options=admin_options,
                index=admin_index,
                format_func=lambda x: next(a[1] for a in health_admins if a[0] == x),
                key=f"admin_edit_{user_id}"
            )
        
        if new_role != "admin" and surveys:
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=[s[0] for s in surveys],
                default=allowed_surveys,
                format_func=lambda x: next(s[1] for s in surveys if s[0] == x),
                key=f"surveys_edit_{user_id}"
            )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                if new_role == "governorate_admin":
                    update_user(user_id, new_username, new_role)
                    # حذف أي تعيينات سابقة وإضافة الجديدة
                    add_governorate_admin(user_id, selected_gov)
                    if new_role != "admin":
                        update_user_allowed_surveys(user_id, selected_surveys)
                else:
                    update_user(user_id, new_username, new_role, selected_admin if new_role == "employee" else None)
                    if new_role != "admin":
                        update_user_allowed_surveys(user_id, selected_surveys)
                del st.session_state.editing_user
                st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_user
                st.rerun()

def manage_surveys():
    st.header("إدارة الاستبيانات")
    
    surveys = get_surveys_list(include_details=True)
    
    for survey in surveys:
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
        with col1:
            st.write(f"**{survey[1]}** (تم الإنشاء في {survey[2]})")
        with col2:
            status = "نشط" if survey[3] else "غير نشط"
            st.write(f"الحالة: {status}")
        with col3:
            if st.button("تعديل", key=f"edit_survey_{survey[0]}"):
                st.session_state.editing_survey = survey[0]
        with col4:
            if st.button("حذف", key=f"delete_survey_{survey[0]}"):
                if delete_survey(survey[0]):
                    st.rerun()
    
    if 'editing_survey' in st.session_state:
        edit_survey(st.session_state.editing_survey)
    
    with st.expander("إنشاء استبيان جديد"):
        create_survey_form()

def edit_survey(survey_id):
    survey = get_surveys_list(survey_id=survey_id, include_details=True)
    if not survey:
        st.error("الاستبيان غير موجود")
        del st.session_state.editing_survey
        return
    
    survey = survey[0]
    fields = get_survey_fields(survey_id)
    
    if 'new_survey_fields' not in st.session_state:
        st.session_state.new_survey_fields = []
    
    with st.form(f"edit_survey_{survey_id}"):
        st.subheader("تعديل الاستبيان")
        
        new_name = st.text_input("اسم الاستبيان", value=survey[1])
        is_active = st.checkbox("نشط", value=bool(survey[3]))
        
        st.subheader("الحقول الحالية")
        
        updated_fields = []
        for field in fields:
            with st.expander(f"حقل: {field[1]} (نوع: {field[2]})"):
                col1, col2 = st.columns(2)
                with col1:
                    new_label = st.text_input("تسمية الحقل", value=field[1], key=f"label_{field[0]}")
                    new_type = st.selectbox(
                        "نوع الحقل",
                        ["text", "number", "dropdown", "checkbox", "date"],
                        index=["text", "number", "dropdown", "checkbox", "date"].index(field[2]),
                        key=f"type_{field[0]}"
                    )
                with col2:
                    new_required = st.checkbox("مطلوب", value=bool(field[4]), key=f"required_{field[0]}")
                    if new_type == 'dropdown':
                        options = "\n".join(json.loads(field[3])) if field[3] else ""
                        new_options = st.text_area(
                            "خيارات القائمة المنسدلة (سطر لكل خيار)",
                            value=options,
                            key=f"options_{field[0]}"
                        )
                    else:
                        new_options = None
                
                updated_fields.append({
                    'field_id': field[0],
                    'field_label': new_label,
                    'field_type': new_type,
                    'field_options': [opt.strip() for opt in new_options.split('\n')] if new_options else None,
                    'is_required': new_required
                })
        
        st.subheader("إضافة حقول جديدة")
        
        for i, field in enumerate(st.session_state.new_survey_fields):
            st.markdown(f"#### الحقل الجديد {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                field['field_label'] = st.text_input("تسمية الحقل", 
                                                   value=field.get('field_label', ''),
                                                   key=f"new_label_{i}")
                field['field_type'] = st.selectbox(
                    "نوع الحقل",
                    ["text", "number", "dropdown", "checkbox", "date"],
                    index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                    key=f"new_type_{i}"
                )
            with col2:
                field['is_required'] = st.checkbox("مطلوب", 
                                                 value=field.get('is_required', False),
                                                 key=f"new_required_{i}")
                if field['field_type'] == 'dropdown':
                    options = st.text_area(
                        "خيارات القائمة المنسدلة (سطر لكل خيار)",
                        value="\n".join(field.get('field_options', [])),
                        key=f"new_options_{i}"
                    )
                    field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("➕ إضافة حقل جديد"):
                st.session_state.new_survey_fields.append({
                    'field_label': '',
                    'field_type': 'text',
                    'is_required': False,
                    'field_options': []
                })
                st.rerun()
        with col2:
            if st.form_submit_button("🗑️ حذف آخر حقل") and st.session_state.new_survey_fields:
                st.session_state.new_survey_fields.pop()
                st.rerun()
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 حفظ التعديلات"):
                all_fields = updated_fields + st.session_state.new_survey_fields
                if update_survey(survey_id, new_name, is_active, all_fields):
                    st.success("تم تحديث الاستبيان بنجاح")
                    st.session_state.new_survey_fields = []
                    del st.session_state.editing_survey
                    st.rerun()
        with col2:
            if st.form_submit_button("❌ إلغاء"):
                st.session_state.new_survey_fields = []
                del st.session_state.editing_survey
                st.rerun()

def create_survey_form():
    if 'create_survey_fields' not in st.session_state:
        st.session_state.create_survey_fields = []
    
    governorates = get_governorates_list()
    
    with st.form("create_survey_form"):
        survey_name = st.text_input("اسم الاستبيان")
        
        selected_governorates = st.multiselect(
            "المحافظات المسموحة",
            options=[g[0] for g in governorates],
            format_func=lambda x: next(g[1] for g in governorates if g[0] == x)
        )
        
        st.subheader("حقول الاستبيان")
        
        for i, field in enumerate(st.session_state.create_survey_fields):
            st.subheader(f"الحقل {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                field['field_label'] = st.text_input("تسمية الحقل", value=field.get('field_label', ''), key=f"new_label_{i}")
                field['field_type'] = st.selectbox(
                    "نوع الحقل",
                    ["text", "number", "dropdown", "checkbox", "date"],
                    index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                    key=f"new_type_{i}"
                )
            with col2:
                field['is_required'] = st.checkbox("مطلوب", value=field.get('is_required', False), key=f"new_required_{i}")
                if field['field_type'] == 'dropdown':
                    options = st.text_area(
                        "خيارات القائمة المنسدلة (سطر لكل خيار)",
                        value="\n".join(field.get('field_options', [])),
                        key=f"new_options_{i}"
                    )
                    field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("إضافة حقل جديد"):
                st.session_state.create_survey_fields.append({
                    'field_label': '',
                    'field_type': 'text',
                    'is_required': False,
                    'field_options': []
                })
        with col2:
            if st.form_submit_button("حذف آخر حقل") and st.session_state.create_survey_fields:
                st.session_state.create_survey_fields.pop()
        with col3:
            if st.form_submit_button("حفظ الاستبيان") and survey_name:
                if save_survey(survey_name, st.session_state.create_survey_fields, selected_governorates):
                    st.session_state.create_survey_fields = []
                    st.rerun()

def display_survey_data(survey_id):
    survey_info = get_response_info(survey_id)
    if not survey_info:
        st.error("الاستبيان المحدد غير موجود")
        return
    
    survey_name = survey_info[1]
    st.subheader(f"بيانات الاستبيان: {survey_name}")

    # الحصول على عدد الإجابات
    responses = get_response_details(survey_id)
    total_responses = len(responses)

    if total_responses == 0:
        st.info("لا توجد بيانات متاحة لهذا الاستبيان بعد")
        return

    # عرض الإحصائيات
    completed_responses = sum(1 for r in responses if r[5])
    regions_count = len(set(r[3] for r in responses))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("إجمالي الإجابات", total_responses)
    with col2:
        st.metric("الإجابات المكتملة", completed_responses)
    with col3:
        st.metric("عدد المناطق", regions_count)

    # تحضير البيانات للعرض
    df = pd.DataFrame(
        [(r[0], r[2], r[3], r[4], r[6], "مكتملة" if r[5] else "مسودة") for r in responses],
        columns=["ID", "المستخدم", "الإدارة الصحية", "المحافظة", "تاريخ التقديم", "الحالة"]
    )
    
    st.dataframe(df)
    
    # زر تصدير شامل لجميع البيانات
    if st.button("تصدير شامل لجميع البيانات إلى Excel", key=f"export_excel_{survey_id}"):
        export_survey_data_to_excel(survey_id, survey_name, responses)

    # عرض تفاصيل إجابة محددة
    selected_response_id = st.selectbox(
        "اختر إجابة لعرض وتعديل تفاصيلها",
        options=[r[0] for r in responses],
        format_func=lambda x: f"إجابة #{x}",
        key=f"select_response_{survey_id}"
    )

    if selected_response_id:
        response_details = get_response_details(selected_response_id)
        if response_details:
            display_response_details(selected_response_id, response_details)

def export_survey_data_to_excel(survey_id, survey_name, responses):
    import re
    from io import BytesIO
    
    filename = re.sub(r'[^\w\-_]', '_', survey_name) + "_كامل_" + datetime.now().strftime("%Y%m%d_%H%M") + ".xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # 1. ورقة ملخص الإجابات
        df = pd.DataFrame(
            [(r[0], r[2], r[3], r[4], r[6], "مكتملة" if r[5] else "مسودة") for r in responses],
            columns=["ID", "المستخدم", "الإدارة الصحية", "المحافظة", "تاريخ التقديم", "الحالة"]
        )
        df.to_excel(writer, sheet_name='ملخص_الإجابات', index=False)
        
        # 2. ورقة تفاصيل جميع الإجابات
        all_details = []
        for response in responses:
            details = get_response_details(response[0])
            for detail in details:
                all_details.append({
                    "ID الإجابة": response[0],
                    "الحقل": detail[2],
                    "القيمة": detail[5],
                    "أدخلها": response[2],
                    "تاريخ الإدخال": response[6],
                    "حالة الإجابة": "مكتملة" if response[5] else "مسودة"
                })
        
        if all_details:
            details_df = pd.DataFrame(all_details)
            details_df.to_excel(writer, sheet_name='تفاصيل_الإجابات', index=False)
        
        # 3. ورقة حقول الاستبيان
        fields = get_survey_fields(survey_id)
        fields_df = pd.DataFrame(
            [(f[1], f[2], json.loads(f[3]) if f[3] else None, "نعم" if f[4] else "لا") for f in fields],
            columns=["اسم الحقل", "نوع الحقل", "الخيارات", "مطلوب"]
        )
        fields_df.to_excel(writer, sheet_name='حقول_الاستبيان', index=False)
        
        # 4. ورقة المستخدمين الذين أدخلوا بيانات
        users_df = pd.DataFrame(
            [(r[2], r[3], r[4], r[6], "مكتملة" if r[5] else "مسودة") for r in responses],
            columns=["المستخدم", "الإدارة الصحية", "المحافظة", "تاريخ التقديم", "الحالة"]
        )
        users_df.drop_duplicates().to_excel(writer, sheet_name='المستخدمين', index=False)
   
    with open(filename, "rb") as f:
        st.download_button(
            label="تنزيل ملف Excel الكامل",
            data=f,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_excel_{survey_id}"
        )
    st.success("تم إنشاء ملف Excel الشامل بنجاح")

def display_response_details(response_id, details):
    st.subheader(f"تفاصيل الإجابة #{response_id}")
    response_info = get_response_info(response_id)
    if response_info:
        st.markdown(f"""
        **الاستبيان:** {response_info[1]}  
        **المستخدم:** {response_info[2]}  
        **الإدارة الصحية:** {response_info[3]}  
        **المحافظة:** {response_info[4]}  
        **تاريخ التقديم:** {response_info[5]}
        """)
        
        updates = {}
        
        with st.form(key=f"edit_response_form_{response_id}"):
            for detail in details:
                detail_id, field_id, label, field_type, options, answer = detail
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown(f"**{label}**")
                with col2:
                    if field_type == 'dropdown':
                        options_list = json.loads(options) if options else []
                        new_value = st.selectbox(
                            label,
                            options_list,
                            index=options_list.index(answer) if answer in options_list else 0,
                            key=f"dropdown_{detail_id}_{response_id}"
                        )
                    else:
                        new_value = st.text_input(
                            label,
                            value=answer,
                            key=f"input_{detail_id}_{response_id}"
                        )
                    
                    if new_value != answer:
                        updates[detail_id] = new_value
            
            col1, col2 = st.columns(2)
            with col1:
                save_clicked = st.form_submit_button("💾 حفظ جميع التعديلات")
                if save_clicked:
                    if updates:
                        success_count = 0
                        for detail_id, new_value in updates.items():
                            if update_response_detail(detail_id, new_value):
                                success_count += 1
                        
                        if success_count == len(updates):
                            st.success("تم تحديث جميع التعديلات بنجاح")
                        else:
                            st.error(f"تم تحديث {success_count} من أصل {len(updates)} تعديلات")
                        st.rerun()
                    else:
                        st.info("لم تقم بإجراء أي تعديلات")
            with col2:
                cancel_clicked = st.form_submit_button("❌ إلغاء التعديلات")
                if cancel_clicked:
                    st.rerun()

def view_data():
    st.header("عرض البيانات المجمعة")
    
    surveys = get_surveys_list()
    
    if not surveys:
        st.warning("لا توجد استبيانات متاحة")
        return
        
    selected_survey = st.selectbox(
        "اختر استبيان",
        surveys,
        format_func=lambda x: x[1],
        key="survey_select"
    )
    
    if selected_survey:
        display_survey_data(selected_survey[0])

def manage_governorates():
    st.header("إدارة المحافظات")
    governorates = get_governorates_list(include_description=True)
    
    for gov in governorates:
        col1, col2, col3, col4 = st.columns([4, 3, 1, 1])
        with col1:
            st.write(f"**{gov[1]}**")
        with col2:
            st.write(gov[2] if gov[2] else "لا يوجد وصف")
        with col3:
            if st.button("تعديل", key=f"edit_gov_{gov[0]}"):
                st.session_state.editing_gov = gov[0]
        with col4:
            if st.button("حذف", key=f"delete_gov_{gov[0]}"):
                if delete_governorate(gov[0]):
                    st.rerun()
    
    if 'editing_gov' in st.session_state:
        edit_governorate(st.session_state.editing_gov)
    
    with st.expander("إضافة محافظة جديدة"):
        with st.form("add_governorate_form"):
            governorate_name = st.text_input("اسم المحافظة")
            description = st.text_area("الوصف")
            
            submitted = st.form_submit_button("حفظ")
            
            if submitted and governorate_name:
                if add_governorate(governorate_name, description):
                    st.rerun()

def edit_governorate(gov_id):
    governorates = get_governorates_list(include_description=True)
    gov = next((g for g in governorates if g[0] == gov_id), None)
    
    if not gov:
        st.error("المحافظة غير موجودة")
        del st.session_state.editing_gov
        return
    
    with st.form(f"edit_gov_{gov_id}"):
        new_name = st.text_input("اسم المحافظة", value=gov[1])
        new_desc = st.text_area("الوصف", value=gov[2] if gov[2] else "")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                if update_governorate(gov_id, new_name, new_desc):
                    st.success("تم تحديث المحافظة بنجاح")
                    del st.session_state.editing_gov
                    st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_gov
                st.rerun()

def delete_governorate(gov_id):
    if check_governorate_has_regions(gov_id):
        st.error("لا يمكن حذف المحافظة لأنها تحتوي على إدارات صحية!")
        return False
    
    if delete_governorate_from_db(gov_id):
        st.success("تم حذف المحافظة بنجاح")
        return True
    else:
        st.error("حدث خطأ أثناء الحذف")
        return False

def manage_regions():
    st.header("إدارة الإدارات الصحية")
    
    regions = get_all_regions()
    
    for reg in regions:
        col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
        with col1:
            st.write(f"**{reg[1]}**")
        with col2:
            st.write(reg[2] if reg[2] else "لا يوجد وصف")
        with col3:
            st.write(reg[3])
        with col4:
            if st.button("تعديل", key=f"edit_reg_{reg[0]}"):
                st.session_state.editing_reg = reg[0]
        with col5:
            if st.button("حذف", key=f"delete_reg_{reg[0]}"):
                if delete_health_admin(reg[0]):
                    st.rerun()
    
    if 'editing_reg' in st.session_state:
        edit_health_admin(st.session_state.editing_reg)
    
    with st.expander("إضافة إدارة صحية جديدة"):
        governorates = get_governorates_list()
        
        if not governorates:
            st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")
            return
            
        with st.form("add_health_admin_form"):
            admin_name = st.text_input("اسم الإدارة الصحية")
            description = st.text_area("الوصف")
            governorate_id = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x))
            
            submitted = st.form_submit_button("حفظ")
            
            if submitted and admin_name:
                if add_health_admin(admin_name, description, governorate_id):
                    st.rerun()

def edit_health_admin(admin_id):
    regions = get_all_regions()
    admin = next((r for r in regions if r[0] == admin_id), None)
    
    if not admin:
        st.error("الإدارة الصحية المطلوبة غير موجودة!")
        del st.session_state.editing_reg
        return
    
    governorates = get_governorates_list()
    
    with st.form(f"edit_admin_{admin_id}"):
        new_name = st.text_input("اسم الإدارة الصحية", value=admin[1])
        new_desc = st.text_area("الوصف", value=admin[2] if admin[2] else "")
        new_gov = st.selectbox(
            "المحافظة",
            options=[g[0] for g in governorates],
            index=[g[0] for g in governorates].index(admin[4]),
            format_func=lambda x: next(g[1] for g in governorates if g[0] == x))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                if update_health_admin(admin_id, new_name, new_desc, new_gov):
                    st.success("تم تحديث الإدارة الصحية بنجاح")
                    del st.session_state.editing_reg
                    st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_reg
                st.rerun()

def delete_health_admin(admin_id):
    if check_admin_has_users(admin_id):
        st.error("لا يمكن حذف الإدارة الصحية لأنها مرتبطة بمستخدمين!")
        return False
    
    if delete_health_admin_from_db(admin_id):
        st.success("تم حذف الإدارة الصحية بنجاح")
        return True
    else:
        st.error("حدث خطأ أثناء الحذف")
        return False
