from __future__ import annotations
import base64
import json
import os
import subprocess
import tempfile
from pydantic import BaseModel
import requests
from dotenv import load_dotenv


BASE_URL = "https://booking.bbdc.sg/bbdc-back-service/api"

HEADERS = {
    'authority': 'booking.bbdc.sg',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'content-type': 'application/json;charset=UTF-8',
    'dnt': '1',
    'jsessionid': '',
    'origin': 'https://booking.bbdc.sg',
    'referer': 'https://booking.bbdc.sg/',
    'sec-ch-ua': '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
}


class CheckIdPasswordResponseData(BaseModel):
    tokenHeader: str
    tokenContent: str
    username: str

class CheckIdPasswordResponse(BaseModel):
    success: bool
    code: int
    data: CheckIdPasswordResponseData

class LoginCaptchaData(BaseModel):
    image: str  # base64-encoded image
    captchaToken: str  # JWT
    verifyCodeId: str
    
class LoginCaptcha(BaseModel):
    success: bool
    # message: str | None = None
    code: int
    data: LoginCaptchaData

class Course(BaseModel):
    courseType: str  # eg. 3C
    accountBal: float
    enrExpiryDateStr: str  # eg. "13-06-2024"
    authToken: str  # Bearer <jwt>

class CoursesData(BaseModel):
    activeCourseList: list[Course]

class Courses(BaseModel):
    success: bool
    # message: str | None = None
    code: int
    data: CoursesData

class SlotMonth(BaseModel):
    slotMonthEn: str  # "Jan'24"

class Slot(BaseModel):
    slotId: int
    slotRefName: str
    slotRefDate: str
    startTime: str
    endTime: str
    slotAvlComputed: bool
    computedSlotAvl: int

    def __lt__(self, other: Slot):
        if self.slotRefDate == other.slotRefDate:
            return self.startTime < other.startTime
        else:
            return self.slotRefDate < other.slotRefDate


class SlotResponseData(BaseModel):
    releasedSlotMonthList: list[SlotMonth]
    releasedSlotListGroupByDay: dict[str, list[Slot]]

    def get_available_sessions_by_session(self, *sessions) -> list[Slot]:

        session_names = [f"SESSION {session}" for session in sessions]
        
        available_slots = []

        for slots in self.releasedSlotListGroupByDay.values():
            for slot in slots:
                if slot.slotRefName in session_names:
                    available_slots.append(slot)

        return sorted(available_slots)

class SlotResponse(BaseModel):
    success: bool
    # message: str | None = None
    code: int
    data: SlotResponseData

def check_id_and_password(*, user_id: str, user_password: str) -> CheckIdPasswordResponse:
    url = f"{BASE_URL}/auth/checkIdAndPass"
    payload = {
        "userId": user_id,
        "userPass": user_password,
    }
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
    return CheckIdPasswordResponse.model_validate(response.json())

def get_login_captcha() -> LoginCaptcha:
    url = f"{BASE_URL}/auth/getLoginCaptchaImage"
    payload = {}
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
    return LoginCaptcha.model_validate(response.json())

def login(*, captcha_token: str, verify_code_id: str, verify_code_value: str, user_id: str, user_password: str) -> CheckIdPasswordResponse:
    url = f"{BASE_URL}/auth/login"
    payload = {
        "captchaToken": captcha_token,
        "verifyCodeId": verify_code_id,
        "verifyCodeValue": verify_code_value,
        "userId": user_id,
        "userPass": user_password,
    }
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
    return CheckIdPasswordResponse.model_validate(response.json())

def list_courses(authorization_header_value: str) -> Courses:
    url = f"{BASE_URL}/account/listAccountCourseType"
    payload = {}
    headers = HEADERS | {'authorization': authorization_header_value}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return Courses.model_validate(response.json())


def list_c3_practical_slots(*, course_type: str, login_token: str, course_token: str) -> SlotResponse:
    url = f"{BASE_URL}/booking/c3practical/listC3PracticalSlotReleased"
    payload = {
        "courseType": course_type,
        "insInstructorId": "",
        "stageSubDesc": "Practical Lesson",
        "subVehicleType": None,
        "subStageSubNo": None
    }
    headers = HEADERS | {
        'authorization': login_token,
        'jsessionid': course_token,
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return SlotResponse.model_validate(response.json())

def solve_captcha(image: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png") as fp:
        fp.write(image)
        fp.flush()
        subprocess.run(["open", fp.name], check=True)
        captcha_value = input("Captcha value: ")
    return captcha_value

def main():
    load_dotenv()

    username = os.environ["BBDC_USERNAME"]
    password = os.environ["BBDC_PASSWORD"]
    course_type = os.environ["BBDC_COURSE"]

    # Indicate that we're logging in
    _ = check_id_and_password(user_id=username, user_password=password)
    
    # Get captcha data
    login_captcha_data = get_login_captcha()

    # Display captcha and solve it
    captcha_data_str = login_captcha_data.data.image.split(',')[1]
    captcha_data = base64.b64decode(captcha_data_str)
    captcha_value = solve_captcha(captcha_data)

    # Login with captcha
    login_response = login(
        captcha_token=login_captcha_data.data.captchaToken,
        verify_code_id=login_captcha_data.data.verifyCodeId,
        verify_code_value=captcha_value,
        user_id=username,
        user_password=password,
    )

    # List available courses
    courses = list_courses(login_response.data.tokenContent)
    
    # Get the course that we want
    course: Course = list(filter(lambda course: course.courseType==course_type, courses.data.activeCourseList))[0]

    # List all slots
    slot_response = list_c3_practical_slots(
        course_type=course_type,
        login_token=login_response.data.tokenContent,
        course_token=course.authToken,
    )

    # Output the data we want
    print(slot_response.data.releasedSlotMonthList)


if __name__ == "__main__":
    main()
