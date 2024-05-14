import invoke_br_agent as agenthelper
import streamlit as st
import datetime
import json
import pandas as pd
from annotated_text import annotated_text

def display_existing_messages():
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def add_user_message_to_session(prompt):
    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

#@st.cache_data(ttl=3600, show_spinner=False) 
def generate_assistant_response(augmented_query):
    primer = f"""
You are a virtual support assistant that is designed to answer user questions based on the information given above each question.It is crucial to cite sources accurately by using the [[number](URL)] notation after the reference. Say "I don't know" if the information is missing and be as detailed as possible. End each sentence with a period is to answer user questions based on the information given above each question.It is crucial to cite sources accurately by using the [[number](URL)] notation after the reference. Say "I don't know" if the information is missing and be as detailed as possible. End each sentence with a period. Please begin.
             """
        
    event = {
        "sessionId": "SESSION5",
        "question": augmented_query,
        "endSession": "false"        
    }
    response = agenthelper.lambda_handler(event)
    message_placeholder = st.empty()
    full_response = ""
    
    
    response_data = json.loads(response['body'])
    print(response_data)
    # Extract the response and trace data
    all_data = format_response(response_data['response'])
    the_response = response_data['trace_data']
    

    #print(all_data)
    with st.chat_message("assistant"):
        st.markdown(the_response)
    
    return the_response

# Function to parse and format response
def format_response(response_body):
    try:
        # Try to load the response as JSON
        data = json.loads(response_body)
        # If it's a list, convert it to a DataFrame for better visualization
        if isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return response_body
    except json.JSONDecodeError:
        # If response is not JSON, return as is
        return response_body

def hide_streamlit_header_footer():
    hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            #root > div:nth-child(1) > div > div > div > div > section > div {padding-top: 0rem;}
            </style>
            """
    st.markdown(hide_st_style, unsafe_allow_html=True)


def main():
    st.set_page_config(
        page_title="Virtual Support Assistant",
        page_icon="👋",
        layout="centered")
    st.title("Virtual Support Assistant")
    annotated_text(("", "powered by Amazon Bedrock"))
    
    hide_streamlit_header_footer()
    display_existing_messages()

    query = st.chat_input("Please enter your query?")
    if query:
        add_user_message_to_session(query)        
        with st.spinner("Thinking..."):                      
            response = generate_assistant_response(query)
            st.session_state["messages"].append(
                {"role": "assistant", "content": response}
    )
    


if __name__ == "__main__":
    main()