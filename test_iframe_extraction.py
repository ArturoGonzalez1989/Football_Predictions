#!/usr/bin/env python3
"""Test iframe extraction with direct navigation"""
import sys
sys.path.insert(0, 'c:\\Users\\agonz\\OneDrive\\Documents\\Proyectos\\Furbo\\betfair_scraper')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Setup Chrome
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')

driver = webdriver.Chrome(options=options)

try:
    # Navigate to iframe stats
    iframe_url = "https://videoplayer.betfair.es/GetPlayer.do?eID=35232966&contentType=viz&contentView=mstats"
    print(f"Navigating to: {iframe_url}")
    driver.get(iframe_url)

    # Wait for body
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    print("✓ Body loaded")

    # Wait for stats
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Shots on target')]"))
        )
        print("✓ Stats element found!")
    except:
        print("× Timeout waiting for stats")
        print(f"Page source length: {len(driver.page_source)}")
        print(f"Page title: {driver.title}")

    time.sleep(2)

    # Try to extract Free kicks
    labels = ["Shots on target", "Free kicks", "Substitutions", "Fouls"]
    for label in labels:
        xpath = f"//*[contains(text(), '{label}')]"
        elements = driver.find_elements(By.XPATH, xpath)

        if elements:
            elem = elements[0]
            try:
                home = elem.find_element(By.XPATH, "./preceding-sibling::*[1]").text.strip()
                away = elem.find_element(By.XPATH, "./following-sibling::*[1]").text.strip()
                print(f"✓ {label}: {home} - {away}")
            except Exception as e:
                print(f"× {label}: Found label but couldn't get siblings - {e}")
        else:
            print(f"× {label}: Not found in DOM")

finally:
    driver.quit()
