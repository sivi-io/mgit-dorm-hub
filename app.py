from streamlit_gsheets import GSheetsConnection

# ... (Auth, Washing Machine, and Mess Tabs are identical to above) ...

with tab3:
    st.header("📓 Private Expense Ledger (Google Sheets)")
    
    # 1. Connect to Google Sheets securely
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 2. Read the current data from the sheet
    try:
        df = conn.read(worksheet="Expenses", ttl=0) # ttl=0 means always fetch fresh data
    except Exception:
        # If the sheet is empty/new, create an empty structure
        df = pd.DataFrame(columns=["Email", "Date", "Category", "Amount", "Description"])

    with st.form("add_expense_gsheets"):
        category = st.selectbox("Category", ["Rent", "College Fees", "Laundry", "Food/Mess", "Other"])
        amount = st.number_input("Amount (₹)", min_value=0)
        desc = st.text_input("Description")
        
        if st.form_submit_button("Save to Cloud"):
            # Create a new row of data
            new_row = pd.DataFrame([{
                "Email": user['email'], 
                "Date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "Category": category, 
                "Amount": amount, 
                "Description": desc
            }])
            
            # Combine old data with new data
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
            # Write it back to Google Sheets
            conn.update(worksheet="Expenses", data=updated_df)
            st.success("Saved securely to Google Cloud!")
            st.rerun()
            
    # 3. Filter and display data for the logged-in user
    if not df.empty:
        user_df = df[df["Email"] == user['email']].drop(columns=["Email"])
        if not user_df.empty:
            st.dataframe(user_df, use_container_width=True)
            st.write(f"**Total Spent: ₹{pd.to_numeric(user_df['Amount']).sum()}**")