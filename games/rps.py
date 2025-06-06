import random

def rock_paper_scissors():
    options = ["rock", "paper", "scissors"]

    while True:
        user_input = input("Choose rock, paper, scissors or type exit to quit: ").lower().strip()
        
        if user_input == "exit":
            print("Thanks for playing!")
            break
        
        if user_input not in options:
            print(f"{user_input} is not an option, please choose rock, paper, scissors or exit to leave")
            continue

        computer_choice = random.choice(options)
        print(f"Computer chose: {computer_choice}")

        if user_input == computer_choice:
            print("Draw")
        elif (
            (user_input == "rock" and computer_choice == "scissors") or
            (user_input == "scissors" and computer_choice == "paper") or
            (user_input == "paper" and computer_choice == "rock")
        ):
            print("You win!")
        else:
            print("You lose!")

rock_paper_scissors()
