/*************************
   Registration elements
**************************/
const nextButtons = document.querySelectorAll(".next-btn")
const backButtons = document.querySelectorAll(".back-btn")
const submit = document.getElementById("submit")

const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const emailInput = document.getElementById("email");
const phoneInput = document.getElementById("phone-number");
const streetAddressInput = document.getElementById("street-address");
const cityInput = document.getElementById("city");
const stateInput = document.getElementById("state");
const zipCodeInput = document.getElementById("zip-code");

const sendOTPBtn = document.getElementById("send-otp-btn");
const verifyOTPBtn = document.getElementById("verify-otp-btn");
const otpSection = document.getElementById("otp-section");
const otpError = document.getElementById("otp-error");

/* Login elements */
const loginSlides = document.querySelectorAll(".login-slide")
const loginUsername = document.getElementById("login-username");
const loginPassword = document.getElementById("login-password");
const loginOTPCodeInput = document.getElementById("login-otp-code");
const loginOtpError = document.querySelector(".login-otp-error");
const loginNext = document.querySelector(".login-next");
const loginVerifyOTPBtn = document.querySelector(".login-verify-otp-btn");
const loginForgotPassword = document.querySelector(".login-forgot-password");
const loginResetSend = document.querySelector(".login-reset-send");
const loginResetSave = document.querySelector(".login-reset-save");
const loginResetUsername = document.getElementById("login-reset-username");
const loginResetPassword = document.getElementById("login-reset-password");
const loginResetError = document.querySelector(".login-reset-error");
const loginResetPasswordError = document.querySelector(".login-reset-password-error");
let loginPurpose = "login";

/* Phone and slide elements */
let currentPhoneReg = "";
let currentPhoneLogin = "";
let currentSlide = 1;

/*************************
     Slide functions
**************************/
function showSlide(slideNumber)
{
    const slides = document.querySelectorAll(".slide");
    slides.forEach(slide => slide.classList.remove("active"));
    const slide = document.getElementById(`slide${slideNumber}`);

    if (slide)
    {
        slide.classList.add("active");
    }

    currentSlide = slideNumber;
}

function showLoginSlide(slideNumber)
{
    loginSlides.forEach(slide => slide.classList.remove("active"));
    const slide = document.getElementById(`login-slide${slideNumber}`);

    if (slide)
    {
        slide.classList.add("active");
    }
}

function errorElement(input)
{
    if (!input)
    {
        return null;
    }

    let error = input.nextElementSibling;

    if (!error || !error.classList.contains("error-message"))
    {
        error = document.createElement("div");
        error.classList.add("error-message");
        input.insertAdjacentElement("afterend", error);
    }

    return error;
}

/*************************
 Login Page event listeners
**************************/
function resetPasswordMessage(passwordValue)
{
    const hasSpecial = /[!@#$%^&*()_+\-=\[\]{}|;:'",.<>/?`~]/;
    if (!passwordValue)
    {
        return "Password cannot be blank.";
    }
    if (passwordValue.length < 8 || passwordValue.length > 15)
    {
        return "Password must be between 8 and 15 characters.";
    }
    if (!/[A-Z]/.test(passwordValue))
    {
        return "Must contain at least one uppercase letter.";
    }
    if (!/[a-z]/.test(passwordValue))
    {
        return "Must contain at least one lowercase letter.";
    }
    if (!/\d/.test(passwordValue))
    {
        return "Must contain at least one number.";
    }
    if (!hasSpecial.test(passwordValue))
    {
        return "Must contain at least one special character.";
    }
    return "";
}

if (loginForgotPassword)
{
    loginForgotPassword.addEventListener("click", (event) => {
        event.preventDefault();
        loginPurpose = "reset";
        showLoginSlide(3);
        if (loginResetUsername)
        {
            loginResetUsername.focus();
        }
    });
}

document.querySelectorAll(".login-back-to-login").forEach((link) => {
    link.addEventListener("click", (event) => {
        event.preventDefault();
        loginPurpose = "login";
        showLoginSlide(1);
    });
});

if (loginResetSend)
{
    loginResetSend.addEventListener("click", async () => {
        const username = loginResetUsername.value.trim();
        if (!username)
        {
            loginResetError.textContent = "Enter your username or email.";
            return;
        }

        let result;
        try
        {
            const response = await fetch("/forgot_password/send", {
                method: "POST",
                body: new URLSearchParams({username})
            });
            result = await response.json();
        }
        catch (error)
        {
            loginResetError.textContent = "Could not send a code. Try again.";
            return;
        }

        if (!result.success)
        {
            loginResetError.textContent = result.message;
            return;
        }

        loginPurpose = "reset";
        currentPhoneLogin = result.phone;
        loginResetError.textContent = "";
        showLoginSlide(2);
        loginOTPCodeInput.focus();
        loginOtpError.textContent = "OTP sent to your registered phone";
    });
}

if (loginResetSave)
{
    loginResetSave.addEventListener("click", async () => {
        const password = loginResetPassword.value;
        const problem = resetPasswordMessage(password);
        if (problem)
        {
            loginResetPasswordError.textContent = problem;
            return;
        }

        const response = await fetch("/forgot_password/update", {
            method: "POST",
            body: new URLSearchParams({password})
        });
        const result = await response.json();

        if (!result.success)
        {
            loginResetPasswordError.textContent = result.message;
            return;
        }

        loginPurpose = "login";
        loginResetPassword.value = "";
        loginResetPasswordError.textContent = "";
        alert(result.message);
        showLoginSlide(1);
    });
}

if(loginNext)
{
    loginNext.addEventListener("click", async () => {
        loginPurpose = "login";
        const username = loginUsername.value.trim();
        const password = loginPassword.value.trim();

        if (!username || !password)
        {
            alert ("Please fill in username and password");
            return;
        }

        const response = await fetch("/login", {
            method: "POST",
            body: new URLSearchParams({username, password})
        });

        const result = await response.json();

        if (!result.success)
        {
            alert(result.message);
            return;
        }

        if (result.twilio_bypassed)
        {
            alert("Login successful!");
            window.location.href = "/dashboard";
            return;
        }

        if (result.otp_sent)
        {
            currentPhoneLogin = result.phone;
            showLoginSlide(2);
            loginOTPCodeInput.focus();
            loginOtpError.textContent = "OTP sent to your registered phone";
        }
    })
}

if(loginVerifyOTPBtn)
{
    loginVerifyOTPBtn.addEventListener("click", async () => {
        const code = loginOTPCodeInput.value.trim();

        if (!code)
        {
            loginOtpError.textContent = "Please enter the OTP.";
            return;
        }

        const verifyUrl = loginPurpose === "reset" ? "/forgot_password/verify" : "/verify_otp";
        const response = await fetch(verifyUrl, {
            method: "POST",
            body: new URLSearchParams({phone: currentPhoneLogin, code})
        });

        const result = await response.json();

        if (!result.success)
        {
            loginOtpError.textContent = result.message;
            return;
        }

        if (loginPurpose === "reset")
        {
            showLoginSlide(4);
            loginResetPassword.focus();
            return;
        }

        alert("Login successful!");
        window.location.href = "/dashboard";
    })
}

/***********************************
 Registration - Validation Functions
************************************/
async function validateUsername(usernameValue)
{
    const usernameError = errorElement(usernameInput);
    const alphaReg = /^[a-zA-Z0-9]+$/;
    const minLength = 5;
    const maxLength = 15;

    if (usernameValue === '')
    {
        usernameError.textContent = 'Username cannot be blank.';
        usernameInput.classList.add('error');
        return false;
    }
    else if (!alphaReg.test(usernameValue))
    {
        usernameError.textContent = 'Username can only contain letters and numbers';
        usernameInput.classList.add('error');
        return false;
    }
    else if (usernameValue.length < minLength || usernameValue.length > maxLength)
    {
        usernameError.textContent = `Username must be a minimum of ${minLength} characters or maximum of ${maxLength} characters long.`;
        usernameInput.classList.add('error');
        return false;
    }

    try
    {
        const response = await fetch(`/check_username?username=${encodeURIComponent(usernameValue)}`);
        const data = await response.json();

        if (data.exists)
        {
            usernameError.textContent = 'Username already exists.';
            usernameInput.classList.add('error');
            return false;
        }
    }
    catch (error)
    {
        usernameError.textContent = 'Could not verify username.';
        usernameInput.classList.add('error');
        return false;
    }

    usernameError.textContent = '';
    usernameInput.classList.remove('error');
    return true;
}

async function validatePassword(passwordValue)
{
    const passwordError = errorElement(passwordInput);
    const hasSpecial = /[!@#$%^&*()_+\-=\[\]{}|;:'",.<>/?`~]/;
    const hasUppercase = /[A-Z]/;
    const hasLowercase = /[a-z]/;
    const hasNumber = /[\d]/;
    const minLength = 8;
    const maxLength = 15;

    if (passwordValue === '')
    {
        passwordError.textContent = 'Password cannot be blank.';
        passwordInput.classList.add('error');
        return false;
    }
    else if (passwordValue.length < minLength || passwordValue.length > maxLength)
    {
        passwordError.textContent = `Password must be between ${minLength} and ${maxLength} characters.`;
        passwordInput.classList.add('error');
        return false;
    }
    else if (!hasUppercase.test(passwordValue))
    {
        passwordError.textContent = 'Must contain at least one uppercase letter.';
        passwordInput.classList.add('error');
        return false;
    }
    else if (!hasLowercase.test(passwordValue))
    {
        passwordError.textContent = 'Must contain at least one lowercase letter.';
        passwordInput.classList.add('error');
        return false;
    }
    else if (!hasNumber.test(passwordValue))
    {
        passwordError.textContent = 'Must contain at least one number.';
        passwordInput.classList.add('error');
        return false;
    }
    else if (!hasSpecial.test(passwordValue))
    {
        passwordError.textContent = 'Must contain at least one special character.';
        passwordInput.classList.add('error');
        return false;
    }

    passwordError.textContent = '';
    passwordInput.classList.remove('error');
    return true;
}

async function validateEmail(emailValue)
{
    const emailError = errorElement(emailInput);
    const emailReg = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const minLength = 5;
    const maxLength = 50;

    if (emailValue === '')
    {
        emailError.textContent = 'Email cannot be blank.';
        emailInput.classList.add('error');
        return false;
    }
    else if (emailValue.length < minLength || emailValue.length > maxLength)
    {
        emailError.textContent = `Email must be between ${minLength} and ${maxLength} characters.`;
        emailInput.classList.add('error');
        return false;
    }
    else if (!emailReg.test(emailValue))
    {
        emailError.textContent = 'Enter a valid email.';
        emailInput.classList.add('error');
        return false;
    }

    try
    {
        const response = await fetch(`/check_email?email=${encodeURIComponent(emailValue)}`);
        const data = await response.json();

        if (data.exists)
        {
            emailError.textContent = 'Email already exists.';
            emailInput.classList.add('error');
            return false;
        }
    }
    catch (error)
    {
        emailError.textContent = 'Could not verify email.';
        emailInput.classList.add('error');
        return false;
    }

    emailError.textContent = '';
    emailInput.classList.remove('error');
    return true;
}

async function validatePhone(phoneValue)
{
    const phoneError = errorElement(phoneInput);
    const phoneReg = /^(\+?\d{1,2}\s?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}$/;

    if (phoneValue === '')
    {
        phoneError.textContent = 'Phone number cannot be blank';
        phoneInput.classList.add('error');
        return false;
    }
    else if (!phoneReg.test(phoneValue))
    {
        phoneError.textContent = 'Enter a valid phone number';
        phoneInput.classList.add('error');
        return false;
    }

    phoneError.textContent = '';
    phoneInput.classList.remove('error');
    return true;
}

function validateStreet(streetValue)
{
    const streetAddressInputError = errorElement(streetAddressInput);
    const streetReg = /^\d+\s+[A-Za-z0-9\s.'-]+$/;

    if (streetValue === '')
    {
        streetAddressInputError.textContent = 'Street cannot be blank.';
        streetAddressInput.classList.add('error');
        return false;
    }
    else if (!streetReg.test(streetValue))
    {
        streetAddressInputError.textContent = 'Enter a valid street address';
        streetAddressInput.classList.add('error');
        return false;
    }

    streetAddressInputError.textContent = '';
    streetAddressInput.classList.remove('error');
    return true;
}

function validateCity(cityValue)
{
    const cityError = errorElement(cityInput);
    const cityReg = /^[A-Za-z]+(?:[\s-'][A-Za-z]+)*$/;

    if (cityValue === '')
    {
        cityError.textContent = 'City cannot be blank.';
        cityInput.classList.add('error');
        return false;
    }
    else if (!cityReg.test(cityValue))
    {
        cityError.textContent = 'Enter a valid city name.';
        cityInput.classList.add('error');
        return false;
    }

    cityError.textContent = '';
    cityInput.classList.remove('error');
    return true;
}



async function validateState(stateValue)
{
    if(!stateValue)
    {
        const stateError = errorElement(stateInput);
        stateError.textContent = "Please select a state";
        stateInput.classList.add("error");
        return false;
    }

    stateInput.classList.remove("error");
    return true;
}

function validateZip(zipValue)
{
    const zipCodeInputError = errorElement(zipCodeInput);
    const zipReg = /^\d{5}(-\d{4})?$/;

    if (zipValue === '')
    {
        zipCodeInputError.textContent = 'Zip code cannot be blank.';
        zipCodeInput.classList.add('error');
        return false;
    }
    else if (!zipReg.test(zipValue))
    {
        zipCodeInputError.textContent = 'Enter a valid zip code';
        zipCodeInput.classList.add('error');
        return false;
    }

    zipCodeInputError.textContent = '';
    zipCodeInput.classList.remove('error');
    return true;
}

async function validateAddress()
{
    const streetValid = validateStreet(streetAddressInput.value);
    const cityValid = validateCity(cityInput.value);
    const stateValid = await validateState(stateInput.value);
    const zipValid = validateZip(zipCodeInput.value);

    return streetValid && cityValid && stateValid && zipValid;
}

/********************************
 Registration - Slide controllers
*********************************/
if(nextButtons.length > 0)
{
    nextButtons.forEach(btn => {
        btn.addEventListener("click", async(e) => {
            e.preventDefault();

            let letProceed = true;

            switch(currentSlide)
            {
                case 1:
                    letProceed = await validateUsername(usernameInput.value.trim());
                    break;
                case 2:
                    letProceed = await validatePassword(passwordInput.value.trim());
                    break;
                case 3:
                    letProceed = await validateEmail(emailInput.value.trim());
                    break;
                case 4:
                    letProceed = await validatePhone(phoneInput.value.trim());
                    const otpMessage = otpError.textContent.toLowerCase();
                    if (!otpMessage.includes("verified"))
                    {
                        otpError.textContent = "Please verify your phone number before continuing.";
                        letProceed = false;
                    }
                    break;
                case 5:
                    letProceed = await validateAddress();
                    break;
            }

            if (letProceed)
            {
                showSlide(currentSlide + 1);
            }
        });
    });
}

if(backButtons.length > 0)
{
    backButtons.forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            if(currentSlide > 1)
            {
                showSlide(currentSlide - 1);
            }
        });
    })
}

/********************************
      OTP - Registration
*********************************/
if(sendOTPBtn)
{
    sendOTPBtn.addEventListener("click", async () => {
        const phone = phoneInput.value.trim();

        if(!phone)
            return;

        const response = await fetch("/send_otp", {
            method: "POST",
            body: new URLSearchParams({phone})
        });

        const result = await response.json();
        if(result.success)
        {
            otpSection.style.display = "block";
            otpError.textContent = "OTP sent to your phone";
            currentPhoneReg = phone;
        }
        else
        {
            otpError.textContent = result.message;
        }
    });
}

if(verifyOTPBtn)
{
    verifyOTPBtn.addEventListener("click", async () => {
        const phone = phoneInput.value.trim();
        const code = document.getElementById("otp-code").value.trim();

        const response = await fetch("/verify_otp", {
            method: "POST",
            body: new URLSearchParams({ phone, code })
        });

        const result = await response.json();
        if (result.success) {
            alert("Phone verified!");
            otpError.textContent = "Phone verified!";
            otpSection.style.display = "none";
            document.querySelector("#slide4 .next-btn").disabled = false;
        }
        else
        {
            otpError.textContent = result.message;
        }
    });
}

/********************************
 Submission Button and Validation
*********************************/
if(submit)
{
    submit.addEventListener("click", async (e) => {
        e.preventDefault();

        const usernameValid = await validateUsername(usernameInput.value.trim());
        const passwordValid = await validatePassword(passwordInput.value.trim());
        const emailValid = await validateEmail(emailInput.value.trim());
        const phoneValid = await validatePhone(phoneInput.value.trim());
        const addressValid = await validateAddress();

        if (!usernameValid || !passwordValid || !emailValid || !phoneValid || !addressValid)
        {
            return;
        }

        const formData = new FormData(document.getElementById("signupForm"));

        const response = await fetch("/register", {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        if(result.success)
        {
            alert("Registration successful");
            window.location.href = result.redirect_url || "/";
        }
        else
        {
            alert("Registration failed: " + result.message);
        }
    });
}

/*************************
  Loading State Dropdown
**************************/
document.addEventListener("DOMContentLoaded", () => {
    const states = [
    ["AL", "Alabama"], ["AK", "Alaska"], ["AZ", "Arizona"], ["AR", "Arkansas"],
    ["CA", "California"], ["CO", "Colorado"], ["CT", "Connecticut"], ["DE", "Delaware"],
    ["FL", "Florida"], ["GA", "Georgia"], ["HI", "Hawaii"], ["ID", "Idaho"],
    ["IL", "Illinois"], ["IN", "Indiana"], ["IA", "Iowa"], ["KS", "Kansas"],
    ["KY", "Kentucky"], ["LA", "Louisiana"], ["ME", "Maine"], ["MD", "Maryland"],
    ["MA", "Massachusetts"], ["MI", "Michigan"], ["MN", "Minnesota"], ["MS", "Mississippi"],
    ["MO", "Missouri"], ["MT", "Montana"], ["NE", "Nebraska"], ["NV", "Nevada"],
    ["NH", "New Hampshire"], ["NJ", "New Jersey"], ["NM", "New Mexico"], ["NY", "New York"],
    ["NC", "North Carolina"], ["ND", "North Dakota"], ["OH", "Ohio"], ["OK", "Oklahoma"],
    ["OR", "Oregon"], ["PA", "Pennsylvania"], ["RI", "Rhode Island"], ["SC", "South Carolina"],
    ["SD", "South Dakota"], ["TN", "Tennessee"], ["TX", "Texas"], ["UT", "Utah"],
    ["VT", "Vermont"], ["VA", "Virginia"], ["WA", "Washington"], ["WV", "West Virginia"],
    ["WI", "Wisconsin"], ["WY", "Wyoming"]
  ];

    const stateSelect = document.getElementById("state");

    states.forEach (([abbr, name]) => {
        const option = document.createElement("option");
        option.value = abbr;
        option.textContent = name;
        stateSelect.appendChild(option);
    });
});
