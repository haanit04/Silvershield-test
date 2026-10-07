
// Grabs All the elements that use .hint-popup-close
const closeBtn = document.querySelectorAll('.hint-popup-close');

// Get element that has both classes
const helpIcon = document.querySelector(".icon.help")
const allHints = document.querySelectorAll('.internet-window-hint, .email-window-hint,.help-box')

// Grab every X button that uses .hint-popup-close
const closeButtons = document.querySelectorAll('.hint-popup-close');

// Loop through each X and attach a click listener
closeButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
        // Hide the box this X sits inside
        btn.parentElement.classList.add('hidden');
    });
});


// Loop to go through each hint so it opens when the user clicks the help icon
helpIcon.addEventListener('click',function(){
    // For all the hints run the function that removes the hidden CSS class
    // This makes all the hints reappear
    allHints.forEach(function(hint){
        hint.classList.remove('hidden');
    });
});


