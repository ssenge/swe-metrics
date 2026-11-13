package orders;

public class Api {
  public Order find(int id) {
    if (id < 0) {
      throw new IllegalArgumentException("negative id");
    }
    return store.load(id);
  }
}
