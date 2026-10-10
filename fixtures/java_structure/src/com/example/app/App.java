package com.example.app;

import com.example.core.Service;
import com.example.util.Strings;

/** Entry point. */
public class App {
    /** Runs the app. */
    public static void main(String[] args) {
        System.out.println(Strings.shout(new Service().name()));
    }

    public String greet(String who) {
        return "{" + who + "}";
    }

    private void hidden() { }
}
