from __future__ import annotations
import base64
import json
import os
import subprocess
import tempfile
from pydantic import BaseModel, Field, ConfigDict, alias_generators
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
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/115.0.0.0 Safari/537.36',
}


class CamelCaseBaseModel(BaseModel):
    model_config = ConfigDict(alias_generator=alias_generators.to_camel)


class CheckIdPasswordResponseData(CamelCaseBaseModel):
    token_header: str
    token_content: str
    username: str


class CheckIdPasswordResponse(CamelCaseBaseModel):
    success: bool
    code: int | None
    data: CheckIdPasswordResponseData


class LoginCaptchaData(CamelCaseBaseModel):
    image: str  # base64-encoded image
    captcha_token: str  # JWT
    verify_code_id: str


class LoginCaptcha(CamelCaseBaseModel):
    success: bool
    # message: str | None = None
    code: int | None
    data: LoginCaptchaData


class Course(CamelCaseBaseModel):
    course_type: str  # eg. 3C
    account_bal: float
    enr_expiry_date_str: str  # eg. "13-06-2024"
    auth_token: str  # Bearer <jwt>


class CoursesData(CamelCaseBaseModel):
    active_course_list: list[Course]


class Courses(CamelCaseBaseModel):
    success: bool
    # message: str | None = None
    code: int | None
    data: CoursesData


class SlotMonth(CamelCaseBaseModel):
    slot_month_en: str = Field(..., example="Jan'24")
    slot_month_ym: str = Field(..., example="202309")


class Slot(CamelCaseBaseModel):
    slot_id: int
    slot_ref_name: str
    slot_ref_date: str
    start_time: str
    end_time: str
    slot_avl_computed: bool
    computed_slot_avl: int

    def __lt__(self, other: Slot):
        if self.slot_ref_date == other.slot_ref_date:
            return self.start_time < other.start_time
        else:
            return self.slot_ref_date < other.slot_ref_date


class SlotResponseData(CamelCaseBaseModel):
    released_slot_month_list: list[SlotMonth] | None = None
    released_slot_list_group_by_day: dict[str, list[Slot]] | None = None

    def get_available_slots_by_sessions(self, *sessions: int) -> list | None:

        session_names = [f"SESSION {session}" for session in sessions]

        if released_slot_list_group_by_day := self.released_slot_list_group_by_day:
            available_slots = []
            for slots in released_slot_list_group_by_day.values():
                for slot in slots:
                    if slot.slot_ref_name in session_names:
                        available_slots.append(slot)
            return sorted(available_slots)
        else:
            return None


class SlotResponse(CamelCaseBaseModel):
    success: bool
    # message: str | None = None
    code: int | None
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


def login(*, captcha_token: str, verify_code_id: str, verify_code_value: str, user_id: str,
          user_password: str) -> CheckIdPasswordResponse:
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


def list_c3_practical_slots(*, course_type: str, login_token: str, course_token: str,
                            released_slot_month: str | None = None) -> SlotResponse:
    url = f"{BASE_URL}/booking/c3practical/listC3PracticalSlotReleased"
    payload = {
        "courseType": course_type,
        "insInstructorId": "",
        "releasedSlotMonth": released_slot_month,
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


def list_c2_practical_slots(*, course_type: str, login_token: str, course_token: str,
                            released_slot_month: str | None = None) -> SlotResponse:
    url = f"{BASE_URL}/booking/c2practical/listPracSlotReleased"
    payload = {
        "courseType": course_type,
        "insInstructorId": "",
        "releasedSlotMonth": released_slot_month,
        "stageSubDesc": "Subject 1.01",
        "subStageSubNo": "1.01",
        "subVehicleType": "Circuit",
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
        captcha_token=login_captcha_data.data.captcha_token,
        verify_code_id=login_captcha_data.data.verify_code_id,
        verify_code_value=captcha_value,
        user_id=username,
        user_password=password,
    )

    # List available courses
    courses = list_courses(login_response.data.token_content)

    # Get the course that we want
    course: Course = list(filter(lambda lesson: lesson.course_type == course_type, courses.data.active_course_list))[0]

    # List all Class 2 slots
    # slot_response = list_c2_practical_slots(
    #     course_type=course_type,
    #     login_token=login_response.data.token_content,
    #     course_token=course.auth_token,
    # )
    #
    # print(slot_response)
    #
    # if slot_response.data.released_slot_list_group_by_day:
    #     print("Class 2 available slots:", slot_response.data.get_available_slots_by_sessions(5, 6))
    # else:
    #     if releasedSlotMonthList := slot_response.data.released_slot_month_list:
    #         for released_slot_month in releasedSlotMonthList:
    #             slots_for_month = list_c2_practical_slots(
    #                 course_type=course_type,
    #                 login_token=login_response.data.token_content,
    #                 course_token=course.auth_token,
    #                 released_slot_month=released_slot_month.slot_month_ym,
    #             )
    #
    #             # Output the data we want
    #             print("Class 2 available slots:", slots_for_month.data.get_available_slots_by_sessions(5, 6))

    # List all Class 3 slots
    slot_response = list_c3_practical_slots(
        course_type=course_type,
        login_token=login_response.data.token_content,
        course_token=course.auth_token,
    )

    if slot_response.data.released_slot_list_group_by_day:
        print("Class 3 available slots:", slot_response.data.get_available_slots_by_sessions(5, 6))
    else:
        if releasedSlotMonthList := slot_response.data.released_slot_month_list:
            for released_slot_month in releasedSlotMonthList:
                print(released_slot_month, "released for Class 3.")

                slots_for_month = list_c3_practical_slots(
                    course_type=course_type,
                    login_token=login_response.data.token_content,
                    course_token=course.auth_token,
                    released_slot_month=released_slot_month.slot_month_ym,
                )

                # Output the data we want
                print("Class 3 available slots:", slots_for_month.data.get_available_slots_by_sessions(5, 6))


if __name__ == "__main__":
    main()
