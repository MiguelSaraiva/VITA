from flask import Flask, render_template, request, jsonify
import pypyodbc as odbc
import requests
import traceback
import logging
import math
import pandas as pd
import asyncio
import concurrent.futures

import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from getpass import getpass
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
import csv
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from dateutil.relativedelta import relativedelta
from selenium.webdriver.common.action_chains import ActionChains
import re

DRIVER_NAME = 'SQL SERVER'
SERVER_NAME='MSI\SQLEXPRESS'
DATABASE_NAME='Vacation_Planner'

connection_string = f"""
    DRIVER={{{DRIVER_NAME}}};
    SERVER={SERVER_NAME};
    DATABASE={DATABASE_NAME};
    Trust_Connection=yes;
"""
mykey = 'BB4D9AA218C6479B84BD6A48DCEAD0E0'
app = Flask(__name__)
app.debug = True

if app.debug:
    app.logger.addHandler(logging.StreamHandler())
    app.logger.setLevel(logging.INFO)

@app.route("/")
def home():
    # Create a new connection
    connection = odbc.connect(connection_string)

    # Create a cursor from the connection
    cursor = connection.cursor()

    # Execute the SQL queries
    cursor.execute("SELECT zone_name FROM Zone_Info ORDER BY CAST(zone_name AS VARCHAR(255))")
    rows = cursor.fetchall()
    zones = [row[0] for row in rows]

    cursor.execute("SELECT poi_name FROM Poi_Info")
    rows = cursor.fetchall()
    vacation_types = [row[0] for row in rows]

    cursor.execute("SELECT name FROM amenities")
    rows = cursor.fetchall()
    amenities = [row[0] for row in rows]

    cursor.execute("SELECT name FROM activities")
    rows = cursor.fetchall()
    activities = [row[0] for row in rows]

    # Close the connection
    connection.close()

    return render_template("home.html", zones=zones, vacation_types=vacation_types, amenities=amenities, activities=activities)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return app.send_static_file(filename)

@app.route('/submit_form', methods=['POST'])
def submit_form(retries=10):

    wdpath = 'C:\Program Files (x86)\chromedriver.exe'
    chrome_options = webdriver.ChromeOptions()
    chrome_options.binary_location = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    chrome_options.add_argument("webdriver.chrome.driver=" + wdpath)
    chrome_options.add_argument("start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=chrome_options)

    data = request.get_json()
    destination = data['destination']
    startDate = data['startDate']
    endDate = data['endDate']
    people = data['people']
    rooms = data['rooms']
    # priorities = data['priorities']
    # amenities = data['amenities']
    # Create a new connection
    connection = odbc.connect(connection_string)

    # Create a cursor from the connection
    cursor = connection.cursor()

    # Get the location id from the database
    cursor.execute("SELECT zone_id FROM municipality_info WHERE zone_name=?", (destination,))
    row = cursor.fetchone()

    driver.get(f'https://www.tripadvisor.com/{row[0]}')
    time.sleep(2)
    wait = WebDriverWait(driver, 3)
    cookies_button = driver.find_element(By.XPATH, '//*[@id="onetrust-accept-btn-handler"]')
    cookies_button.click()
    time.sleep(3)
    hotels_button = driver.find_element(By.LINK_TEXT, 'Hotels')
    hotels_button.click()
    time.sleep(5)

    current_date = datetime.strptime("2023-08-01", "%Y-%m-%d")
        
    startDate = datetime.strptime(startDate, "%Y-%m-%d")
    endDate = datetime.strptime(endDate, "%Y-%m-%d")

    startDate_month_name = startDate.strftime('%B')
    endDate_month_name = startDate.strftime('%B')
        
    try:
        next_button = driver.find_element(By.CSS_SELECTOR, '[aria-label="Next month"]')
    except NoSuchElementException:
        print("Error: NoSuchElementException, Restarting...")
        driver.quit()
        time.sleep(2)
        return submit_form(retries-1)
        
    except StaleElementReferenceException:
        time.sleep(2)
        print("StaleElementReferenceException encountered. Retrying...")
        next_button = driver.find_element(By.CSS_SELECTOR, '[aria-label="Next month"]')

    if current_date.month != startDate.month or current_date.year != startDate.year:
        months_diff = (startDate.year - current_date.year) * 12 + startDate.month - current_date.month
        print('MONTHS DIFF: ' + str(months_diff))
        for _ in range(months_diff):
            next_button.click()
            current_date = current_date + relativedelta(months=+1)
            time.sleep(1)
                
    print(current_date.month)
    print(startDate.month)
    print("START DATE IS " + startDate.strftime("%a %b %d %Y"))
    if current_date.month == startDate.month and current_date.year == startDate.year:
        print("Desired date found:", current_date)
        time.sleep(2)
            
        try:
            checkin_date = driver.find_element(By.CSS_SELECTOR, '[aria-label="' + startDate_month_name + " " + str(startDate.day) + ", " + str(startDate.year) + '"]')
            checkin_date.click()
            time.sleep(2)
            checkout_date = driver.find_element(By.CSS_SELECTOR, '[aria-label="' + endDate_month_name + " " + str(endDate.day) + ", " + str(endDate.year) + '"]')
            checkout_date.click()

        except NoSuchElementException:
                startDate_formatted = startDate.strftime("%a %b %d %Y")
                print(startDate_formatted)
                checkin_date = driver.find_element(By.CSS_SELECTOR, f'[aria-label="{startDate_formatted}"]')
                checkin_date.click()
                time.sleep(2)
                endDate_formatted = endDate.strftime("%a %b %d %Y")
                checkout_date = driver.find_element(By.CSS_SELECTOR, f'[aria-label="{endDate_formatted}"]')
                checkout_date.click()
                print('F')

        time.sleep(3)
                
        initial_people = 2
        initial_rooms = 1

        # Calculate the maximum number of iterations needed
        max_diff = max(int(people) - initial_people, int(rooms) - initial_rooms)

        for _ in range(max_diff):

            if int(people) != initial_people:
                while initial_people < int(people):
                    try:
                        plusadults_button = driver.find_element(By.CSS_SELECTOR, '[data-automation="adultsMore"]')
                        plusadults_button.click()                  
                        time.sleep(1)
                    except NoSuchElementException:
                        plusadults_button = driver.find_element(By.CSS_SELECTOR, '[aria-label="Set adult count to one more"]')
                        plusadults_button.click()                   
                        time.sleep(1)
                    initial_people += 1
                    # Break the while loop if the desired number of people is reached
                    if int(people) == initial_people:
                        break

            time.sleep(1)

            if int(rooms) != initial_rooms:
                while initial_rooms < int(rooms):
                    try:
                        plusroom_button = driver.find_element(By.CSS_SELECTOR, '[data-automation="roomsMore"]')
                        plusroom_button.click()
                        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, '[data-testid="nav_next"]')))
                        time.sleep(1)
                    except NoSuchElementException:
                        plusroom_button = driver.find_element(By.CSS_SELECTOR, '[aria-label="Set rooms to one more"]')
                        plusroom_button.click()
                        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, '[data-testid="nav_next"]')))
                        time.sleep(1)
                    initial_rooms += 1
                    # Break the while loop if the desired number of rooms is reached
                    if int(rooms) == initial_rooms:
                        break

        # End the for loop if both the desired number of people and rooms are reached
            if int(people) == initial_people and int(rooms) == initial_rooms:
                break
        
    try:
        update_button = driver.find_element(By.CSS_SELECTOR, '[data-automation="guestsUpdateBtn"]')
        update_button.click()
    except NoSuchElementException:
        update_button = driver.find_element(By.CSS_SELECTOR, '[class="rmyCe _G B- z _S c Wc wSSLS jWkoZ sOtnj"]')
        update_button.click()

    time.sleep(5)
    
    # # Step 1: Locate the slider element
    # try:
    #     slider = driver.find_element(By.CSS_SELECTOR, '[class="rkVKB _Q t s _S V f M wSSLS Rjtte"]')
    # except NoSuchElementException:
    #    slider = driver.find_element(By.CSS_SELECTOR, '[class="YmHtu _Q t l s _S wSSLS xRQxf"]')

    # slider_size = slider.size
    # slider_width = slider_size['width']

    # slider_width = slider.size['width']

    # import re

    # # Step 2: Get the current left property value
    # current_left = slider.get_attribute('style')

    # # Extract the numeric value using regular expressions
    # current_left_value = float(re.search(r'([\d.]+)%', current_left).group(1))

    # # Step 3: Calculate the distance to move the slider
    # desired_distance_px = 222 * 0.85
    # distance_to_move_px = desired_distance_px - (current_left_value / 100) * slider_width

    # # Step 4: Move the slider
    # action = ActionChains(driver)
    # action.click_and_hold(slider).move_by_offset(distance_to_move_px, 0).release().perform()

    time.sleep(10)
    best_value_hotel_names = []
    best_value_hotel_prices = []
    # ranking_button = driver.find_elements(By.CSS_SELECTOR, '[class="jvgKF B1 Z S4"]')[1]
    # ranking_button.click()
    # time.sleep(1)
    # best_value_button = driver.find_element(By.CSS_SELECTOR, '[class="qyYXh S4 H3 option rHING DRQRv"]')
    # best_value_button.click()
    time.sleep(5)
    star4 = driver.find_element(By.XPATH, "//span[contains(text(), '4 Star')]/ancestor::div/preceding-sibling::div/label/input")
    driver.execute_script("arguments[0].scrollIntoView();", star4)
    driver.execute_script("arguments[0].click();", star4)
    time.sleep(2)
    star5 = driver.find_element(By.XPATH, "//span[contains(text(), '5 Star')]/ancestor::div/preceding-sibling::div/label/input")
    driver.execute_script("arguments[0].scrollIntoView();", star5)
    driver.execute_script("arguments[0].click();", star5)
    time.sleep(5)
    for i in range(3, 40):
        try:
            try:
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span/span/span')                                                      
                # hotel_price_element = driver.find_element(By.XPATH, /html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/span/span/span/div/div/div[2]/div[1]/div/div/div[1]/a/div/div[1]/div/span[2]/span/span)
                best_value_hotel_name = hotel_name_element.text
                best_value_hotel_price = hotel_price_element.get_attribute('innerHTML') 

                print(f"Hotel Name: {best_value_hotel_name} - {best_value_hotel_price}")
                #print(f"Hotel Price: {hotel_price}")
            except StaleElementReferenceException:
                print("StaleElementReferenceException encountered. Retrying...")
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span/span/span')                                                      
                # hotel_price_element = driver.find_element(By.XPATH, /html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/span/span/span/div/div/div[2]/div[1]/div/div/div[1]/a/div/div[1]/div/span[2]/span/span)
                best_value_hotel_name = hotel_name_element.text
                best_value_hotel_price = hotel_price_element.get_attribute('innerHTML') 
        except NoSuchElementException:
            try:
                if i > 3:
                    break
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a/div')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span[2]/span/span')
                                                                                                                    
                # hotel_price_element = driver.find_element(By.XPATH, /html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/span/span/span/div/div/div[2]/div[1]/div/div/div[1]/a/div/div[1]/div/span[2]/span/span)
                best_value_hotel_name = hotel_name_element.text
                best_value_hotel_price = hotel_price_element.get_attribute('innerHTML') 
                print(f"Hotel Name: {best_value_hotel_name} - {best_value_hotel_price}")
                #print(f"Hotel Price: {hotel_price}")
            except StaleElementReferenceException:
                print("StaleElementReferenceException encountered. Retrying...")
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a/div')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span[2]/span/span') 

                best_value_hotel_name = hotel_name_element.text
                best_value_hotel_price = hotel_price_element.get_attribute('innerHTML')

            except NoSuchElementException:
                print("StaleElementReferenceException encountered. Retrying...")
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[2]/div[1]/div/div/div[2]/div[3]/div[2]/div[5]/div[{i}]/div/div[1]/div[2]/div[1]/div/div/a')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[2]/div[1]/div/div/div[2]/div[3]/div[2]/div[5]/div[{i}]/div/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div/div[1]/div[1]/div[2]') 

                best_value_hotel_name = hotel_name_element.text
                best_value_hotel_price = hotel_price_element.get_attribute('innerHTML')
        
        best_value_hotel_names.append(best_value_hotel_name)
        best_value_hotel_prices.append(best_value_hotel_price)

        best_value_hotel_data = {
                    'Hotel Name': best_value_hotel_names,
                    'Hotel Price': best_value_hotel_prices
                    }
    time.sleep(3)
    best_ranking_hotel_names = []
    best_ranking_hotel_prices = []
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    ranking_button = driver.find_element(By.CSS_SELECTOR, '[class="tfNjP R2"]')
    ranking_button.click()
    time.sleep(1)
    best_ranking_button = driver.find_element(By.CSS_SELECTOR, '[class="biGQs _P fOtGX"]')
    best_ranking_button.click()
    time.sleep(5)
    star4 = driver.find_element(By.XPATH, "//span[contains(text(), '4 Star')]/ancestor::div/preceding-sibling::div/label/input")
    driver.execute_script("arguments[0].scrollIntoView();", star4)
    driver.execute_script("arguments[0].click();", star4)
    time.sleep(2)
    star5 = driver.find_element(By.XPATH, "//span[contains(text(), '5 Star')]/ancestor::div/preceding-sibling::div/label/input")
    driver.execute_script("arguments[0].scrollIntoView();", star5)
    driver.execute_script("arguments[0].click();", star5)
    time.sleep(7)
    for i in range(3, 40):
        try:
            try:
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span/span/span')                                                      
                # hotel_price_element = driver.find_element(By.XPATH, /html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/span/span/span/div/div/div[2]/div[1]/div/div/div[1]/a/div/div[1]/div/span[2]/span/span)
                best_ranking_hotel_name = hotel_name_element.text
                best_ranking_hotel_price = hotel_price_element.get_attribute('innerHTML') 

                print(f"Hotel Name: {best_ranking_hotel_name} - {best_ranking_hotel_price}")
                #print(f"Hotel Price: {hotel_price}")
            except StaleElementReferenceException:
                print("StaleElementReferenceException encountered. Retrying...")
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span/span/span')                                                      
                # hotel_price_element = driver.find_element(By.XPATH, /html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/span/span/span/div/div/div[2]/div[1]/div/div/div[1]/a/div/div[1]/div/span[2]/span/span)
                best_ranking_hotel_name = hotel_name_element.text
                best_ranking_hotel_price = hotel_price_element.get_attribute('innerHTML') 
        except NoSuchElementException:
            try:
                if i > 3:
                    break
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a/div')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span[2]/span/span')
                                                                                                                    
                # hotel_price_element = driver.find_element(By.XPATH, /html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[3]/span/span/span/div/div/div[2]/div[1]/div/div/div[1]/a/div/div[1]/div/span[2]/span/span)
                best_ranking_hotel_name = hotel_name_element.text
                best_ranking_hotel_price = hotel_price_element.get_attribute('innerHTML') 
                print(f"Hotel Name: {best_ranking_hotel_name} - {best_ranking_hotel_price}")
                #print(f"Hotel Price: {hotel_price}")
            except StaleElementReferenceException:
                print("StaleElementReferenceException encountered. Retrying...")
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/header/div/div/a/div')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[1]/main/div[3]/div/div[2]/div/div[1]/div[2]/div[1]/div/div[{i}]/span/span/span/div/div/div/div[2]/div[1]/div/div/div[1]/a/div[1]/div[1]/div/div/span[2]/span/span') 

                best_ranking_hotel_name = hotel_name_element.text
                best_ranking_hotel_price = hotel_price_element.get_attribute('innerHTML')

            except NoSuchElementException:
                print("StaleElementReferenceException encountered. Retrying...")
                hotel_name_element = driver.find_element(By.XPATH, f'/html/body/div[2]/div[1]/div/div/div[2]/div[3]/div[2]/div[5]/div[{i}]/div/div[1]/div[2]/div[1]/div/div/a')
                hotel_price_element = driver.find_element(By.XPATH, f'/html/body/div[2]/div[1]/div/div/div[2]/div[3]/div[2]/div[5]/div[{i}]/div/div[1]/div[2]/div[2]/div[1]/div/div/div[1]/div/div[1]/div[1]/div[2]') 

                best_ranking_hotel_name = hotel_name_element.text
                best_ranking_hotel_price = hotel_price_element.get_attribute('innerHTML')
        
        best_ranking_hotel_names.append(best_ranking_hotel_name)
        best_ranking_hotel_prices.append(best_ranking_hotel_price)

        best_ranking_hotel_data = {
                    'Hotel Name': best_ranking_hotel_names,
                    'Hotel Price': best_ranking_hotel_prices
                    }  
    time.sleep(10)
    driver.get(f'https://www.tripadvisor.com/{row[0]}')
    time.sleep(5)
    wait = WebDriverWait(driver, 3)
    activities_button = driver.find_element(By.LINK_TEXT, 'Things to Do')
    activities_button.click()
    time.sleep(10)
    try:
        all_button = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[1]/section[4]/div/div/div[1]/div/div[1]/div/div/div[1]/span[1]/span/div/div/div[2]/a')
        link = all_button.get_attribute("href")
         # Navigate to the copied link
        driver.get(link)

    except NoSuchElementException:
        print("Error: NoSuchElementException, Restarting...")
        driver.quit()
        time.sleep(2)
        return submit_form(retries-1)
        

    time.sleep(10)
        
    all_budgets = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/div[3]/div/div/div[2]/button/span/div')
    all_budgets.click()

    free_activities_button = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/div[3]/div/div/div[2]/ul/li[1]/div/span/div[1]/label/span')

    driver.execute_script("arguments[0].scrollIntoView();", free_activities_button)
    driver.execute_script("arguments[0].click();", free_activities_button)

    time.sleep(10)
    free_activity_names = []
    activity_name_elements = driver.find_elements(By.CSS_SELECTOR, '[class="XfVdV o AIbhI"]')
    iteration = 0
    max_iterations = 7
    try:
        while iteration < max_iterations:
            for i in range(len(activity_name_elements)):
                try:
                    all_budgets = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/div[3]/div/div/div[2]/button/span/div')
                    free_activities_button = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/div[3]/div/div/div[2]/ul/li[1]/div/span/div[1]/label/span')
                    activity_name_elements = driver.find_elements(By.CSS_SELECTOR, '[class="XfVdV o AIbhI"]')
                    activity_name = activity_name_elements[i].text
                    free_activity_names.append(activity_name)
                    print(f"Hotel Name: {activity_name}")
                except NoSuchElementException:
                    break
                except StaleElementReferenceException:
                    break
            else:
                i = -1
            if iteration < max_iterations:
                if i == -1:
                    if iteration == 0:
                        i = 0
                        iteration += 1
                        url = driver.current_url
                        x = url.find('-zft')
                        y = 30 * iteration
                        print(y)
                        new_url = url[:x] + f'-zft-oa{y}-' + url[x + 4:]
                        driver.get(new_url)
                        time.sleep(5)
                    if iteration > 0 :
                        i = 0
                        o = iteration
                        iteration += 1
                        url = driver.current_url
                        y = 30 * iteration
                        x = url.find('-zft-oa')               
                        print(y)
                        new_url = url.replace(f'oa{30 * o}', f'oa{y}')
                        driver.get(new_url)
                        time.sleep(5)
    except StaleElementReferenceException:
        pass            
    time.sleep(5)
    all_budgets = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/div[4]/div/div/div[2]/button/span/div')
    all_budgets.click()
    time.sleep(2)
    free_activities_button = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/div[4]/div/div/div[2]/ul/li[5]/div/span/div[1]/label/span')
    driver.execute_script("arguments[0].scrollIntoView();", free_activities_button)
    driver.execute_script("arguments[0].click();", free_activities_button)

    time.sleep(3)
    paid_activities_button = driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div[3]/div/div[2]/div[2]/div[2]/div/div/div[2]/div/div[1]/div[1]/div[2]/div/div[2]/div[4]/div/div/div[2]/ul/li[1]/div/span/div[1]/label/span')
    driver.execute_script("arguments[0].scrollIntoView();", paid_activities_button)
    driver.execute_script("arguments[0].click();", paid_activities_button)

    time.sleep(10)
    paid_activity_names = []
    activity_name_elements = driver.find_elements(By.CSS_SELECTOR, '[class="XfVdV o AIbhI"]')
    iteration = 0
    max_iterations = 9
    while iteration < max_iterations:
        activity_name_elements = driver.find_elements(By.CSS_SELECTOR, '[class="XfVdV o AIbhI"]')
        for i in range(len(activity_name_elements)):
            try:
                activity_name = activity_name_elements[i].text
                paid_activity_names.append(activity_name)
                print(f"Hotel Name: {activity_name}")
            except NoSuchElementException:
                break
            except StaleElementReferenceException:
                break
        else:
            i = -1

        if i == -1:
            if iteration == 0:
                i = 0
                iteration += 1
                url = driver.current_url
                x = url.find('-zft')
                y = 30 * iteration
                print(y)
                new_url = url[:x] + f'-zft-oa{y}-' + url[x + 4:]
                driver.get(new_url)
                time.sleep(5)
            if iteration > 0 :
                i = 0
                o = iteration
                iteration += 1
                url = driver.current_url
                y = 30 * iteration
                x = url.find('-zft-oa')               
                print(y)
                new_url = url.replace(f'oa{30 * o}', f'oa{y}')
                driver.get(new_url)
                time.sleep(5)

        else:
            break

            

        print(f"Current iteration: {iteration}, i: {i}")
    paid_activity_names = [activity for activity in paid_activity_names if activity not in free_activity_names]

    activity_data = {
                    'Free Activity Name': free_activity_names,
                    'Paid Activity Name': paid_activity_names
                    }


    response_data = {
                     'best_ranking_hotel_data': best_ranking_hotel_data,
                     'best_value_hotel_data': best_value_hotel_data,
                     'activity_data': activity_data
                     }
    
    return jsonify(response_data)

# @app.route('/submit_form', methods=['POST'])
# def submit_form():
#     return("Yes!")

    # except Exception as e:
    #     app.logger.error(traceback.format_exc())
    #     return jsonify({'error': 'An unexpected error occurred', 'detail': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

#Zone coords w/ google maps -> get up to 50 hotels within 10km. Retrieve Name & address. Query tripadvisor and get locationid. go to tripadvisor/locationid and scrape the price using the date the user says.
#For testing purposes, and to not exhaust the api limits, the scraping should be tested with the location id 195643 -> Hotel Avenida Palace in Lisbon.