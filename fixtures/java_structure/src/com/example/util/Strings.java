package com.example.util;

import com.example.core.Service;

/** String helpers. */
public final class Strings {
    private Strings() { }

    /** Upper-cases. */
    public static String shout(String s) { return s.toUpperCase() + '}'; }

    public static String trim(String s) { return s.trim(); }

    // a line comment, not javadoc
    public static Service service() { return new Service(); }

    /* block comment, not javadoc */
    public enum Mode { LOUD, QUIET }
}
