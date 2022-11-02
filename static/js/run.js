function neowText(header, bodyText) {
    var headerText = document.getElementById("neow-header").innerHTML;
    var contentText = document.getElementById("neow-body-content").innerHTML;

    if (headerText == header && bodyText == contentText) {
        neowReset();
    } else {
        // Set the header
        document.getElementById("neow-header").innerHTML = header;
        // Hide the original content
        document.getElementById("neow-body-original").className = "message-body hidden";
        // Set the new content and make it appear
        document.getElementById("neow-body-content").innerHTML = bodyText;
        document.getElementById("neow-body-new").className = "message-body";
    }
}

function neowReset() {
    document.getElementById("neow-header").innerHTML = "Neow bonus";
    document.getElementById("neow-body-new").className = "message-body hidden";
    document.getElementById("neow-body-original").className = "message-body";
}

document.onkeydown = navigationKeys;

function navigationKeys(e) {
    e = e || window.event;

    if (e.keyCode == '37') {
        // left arrow key
        if (document.getElementById("hrefPrevRun") != null){
            document.getElementById("hrefPrevRun").click();
        }
    }
    else if (e.keyCode == '39') {
        // right arrow key
        if (document.getElementById("hrefNextRun") != null){
            document.getElementById("hrefNextRun").click();
        }
    }
}
