from lib import step, Step

@step(
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[]
)
class Step1(Step[str, str]):
    def call(self, input_data: str) -> str:
        print(input_data)
        return "transformed"


@step(
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[Step1]
)
class Step2(Step[str, str]):
    def __init__(self, step1: Step1):
        self.step1 = step1

    def call(self, input_data: str) -> str:
        print("This was the output of step 1", self.step1.output)
        return "transformed"

@step(
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[Step2]
)
class Step3(Step[str, str]):
    def __init__(self, step2: Step2):
        self.step2 = step2

    def call(self, input_data: str) -> str:
        print("This was the output of step 2:", self.step2.output)
        return "transformed"