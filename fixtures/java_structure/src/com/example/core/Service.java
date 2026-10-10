package com.example.core;

import com.example.util.Strings;

public class Service {
    private final Repo repo = new Repo();

    /** Creates a service. */
    public Service() { }

    /**
     * The service name.
     * @return the name
     */
    @Deprecated
    public String name() {
        Runnable r = new Runnable() {
            public void run() { }
        };
        r.run();
        return Strings.trim(repo.find());
    }

    @Override
    public String toString() { return "Service"; }

    /** A nested listener. */
    public interface Listener {
        void changed(String what);
    }
}
