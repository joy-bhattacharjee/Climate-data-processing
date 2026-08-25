async function runStep(step) {

    const logConsole =
        document.getElementById(
            "logConsole"
        );


    logConsole.textContent +=
        "\nStarting step: " + step;


    try {

        const response =
            await fetch(
                "/api/run/" + step,
                {
                    method: "POST"
                }
            );


        const data =
            await response.json();


        logConsole.textContent +=
            "\n" + data.message;


    } catch (error) {

        logConsole.textContent +=
            "\nERROR: " + error.message;

    }

}


document
    .querySelectorAll(".run-button")
    .forEach(
        button => {

            button.addEventListener(
                "click",

                function() {

                    runStep(
                        this.dataset.step
                    );

                }
            );

        }
    );